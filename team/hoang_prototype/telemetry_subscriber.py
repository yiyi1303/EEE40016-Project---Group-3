import sys
import threading
from datetime import datetime

from paho.mqtt import client as mqtt

# Terminal colours.
GREEN = "\033[92m"   # Incoming messages.
CYAN = "\033[96m"    # Outgoing messages acknowledged by the broker.
RED = "\033[91m"     # Errors.
RESET = "\033[0m"    # Restore the normal colour.


# BROKER AND TOPIC SETTINGS

# Connect to Mosquitto running on this computer.
BROKER = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

# Must match the broker configuration and publisher.
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 1884
# [Changed for integration] the broker and port can be given on the command line, e.g.
#   py telemetry_subscriber.py 192.168.43.20 1883
# to test between the laptop and the Pi without editing the file.

# Receive the publisher's messages on this topic.
TOPIC = "smartgrid_mqtt_test"

# Send manual replies back to the publisher on this topic.
REPLY_TOPIC = f"{TOPIC}/rep"

# Must differ from the publisher's client ID.
CLIENT_ID = "smartgrid-subscriber"

# Maximum wait for connection or broker acknowledgement.
TIMEOUT_SECONDS = 10


# CONENCTION STATUS

# Tracks whether the client is connected to the broker.
connected = threading.Event()

# Signals that the broker answered our connection request.
connection_response = threading.Event()


# MQTT CALLBACKS

# Runs when the broker responds to a connection request.
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connected.set()
        print("\nConnected to MQTT broker!")

        # Subscribe after every connection, including reconnections.
        result, message_id = client.subscribe(TOPIC, qos=1)

        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"Subscription requested: {TOPIC}")
        else:
            print(f"Subscription request failed: {result}")
    else:
        connected.clear()
        print(f"\nConnection rejected: {reason_code}")

    # Let the main program continue after receiving a response.
    connection_response.set()


# Runs when the broker confirms or rejects the subscription.
def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print("\nBroker rejected the telemetry subscription.")
    else:
        print(f"\nTelemetry subscription confirmed: {TOPIC}")


# Runs whenever a message arrives on the subscribed topic.
def on_message(client, userdata, message):
    # Convert received bytes into readable text.
    # Replace invalid characters instead of crashing.
    payload = message.payload.decode("utf-8", errors="replace")

    # This is the local reception time, not the measurement time.
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{GREEN}[{timestamp}] Received on {message.topic}: {payload}{RESET}")

    # Restore the reply prompt after displaying an incoming message.
    print("Write your reply here: ", end="", flush=True)


# Runs when the client disconnects from the broker.
def on_disconnect(client, userdata, flags, reason_code, properties):
    connected.clear()
    print(f"\nDisconnected: {reason_code}")

    if reason_code != 0:
        print("Unexpected disconnection; MQTT will try to reconnect.")


# CREATE MQTT CLIENT

def create_client():
    # Use Paho's version 2 callback interface.
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
    )

    # To use a broker that requires login, uncomment the line below
    # and replace the placeholders with your assigned credentials.
    # client.username_pw_set("YOUR_USERNAME", "YOUR_PASSWORD")

    # Keep it commented out for our current local anonymous broker.
    # Set credentials before calling connect() or connect_async().

    # Assign the functions that handle MQTT events.
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Gradually increase the delay between reconnection attempts.
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    # Our local broker allows connections without credentials.
    return client


# SEND MANUAL REPLY

def reply_messages(client):
    while True:
        text = input("Write your reply here: ").strip()

        # Type quit to stop the subscriber.
        if text.lower() == "quit":
            break

        # Skip blank replies.
        if not text:
            continue

        # Avoid sending new replies while disconnected.
        if not connected.is_set():
            print("Not connected. Wait for reconnection and try again.")
            continue

        # Send the reply with QoS 1 to request broker acknowledgement.
        # Do not retain this test reply for future subscribers.
        result = client.publish(
            REPLY_TOPIC,
            payload=text,
            qos=1,
            retain=False,
        )

        # Check whether Paho accepted the request.
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Reply request failed: {result.rc}")
            continue

        try:
            # Wait while the background thread handles MQTT traffic.
            result.wait_for_publish(timeout=TIMEOUT_SECONDS)

            if result.is_published():
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"{CYAN}[{timestamp}] REPLIED - Broker acknowledged{RESET}")
            else:
                # A missing acknowledgement does not prove delivery failed.
                print("No acknowledgement within 10 seconds; delivery uncertain.")

        except RuntimeError as error:
            print(f"Reply error: {error}")


# RUN AND CLEAN UP

def main():
    client = create_client()

    try:
        print(f"Connecting to {BROKER}:{PORT}...")

        # Begin connecting in the background.
        client.connect_async(BROKER, PORT, keepalive=30)

        # Handle incoming messages and replies in a background thread,
        # allowing you to type in the main thread.
        client.loop_start()

        # Stop waiting if the broker does not respond in time.
        if not connection_response.wait(timeout=TIMEOUT_SECONDS):
            print("Connection timed out. Check that Mosquitto is running.")
            return

        if not connected.is_set():
            print("Connection was rejected. Check the broker configuration.")
            return

        print("Wait for subscription confirmation before sending telemetry.")
        print("Type a reply and press Enter. Type quit to stop.")
        reply_messages(client)

    except (KeyboardInterrupt, EOFError):
        # Handle Ctrl+C or closed terminal input cleanly.
        print("\nStopping subscriber...")

    except OSError as error:
        print(f"Network error: {error}")

    finally:
        # Disconnect, then stop the background network thread.
        client.disconnect()
        client.loop_stop()
        print("Subscriber stopped.")


# Run only when this file is executed directly.
if __name__ == "__main__":
    main()