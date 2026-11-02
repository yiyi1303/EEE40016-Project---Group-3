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

# 127.0.0.1 means the broker runs on this same computer.
BROKER = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

# Must match the port in mosquitto_local.conf.
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 1884
# [Changed for integration] the broker and port can be given on the command line, e.g.
#   py telemetry_publisher.py 192.168.43.20 1883
# to test between the laptop and the Pi without editing the file.

# Send messages to this topic.
TOPIC = "smartgrid_mqtt_test"

# Receive the subscriber's replies on this topic.
REPLY_TOPIC = f"{TOPIC}/rep"

# Each running MQTT client needs a different ID.
CLIENT_ID = "smartgrid-publisher"

# How long to wait for a connection or broker acknowledgement.
TIMEOUT_SECONDS = 10


# CONNECTION STATUS

# An Event lets the main program check connection status safely
# while MQTT callbacks run in a separate background thread.
connected = threading.Event()

# Indicates that the broker has responded to our connection request.
connection_response = threading.Event()


# MQTT CALLBACKS

# Paho calls this when the broker responds to a connection request.
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connected.set()
        print("\nConnected to MQTT broker!")

        # Subscribe again after every successful connection,
        # including reconnections.
        result, message_id = client.subscribe(REPLY_TOPIC, qos=1)

        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"Subscription requested: {REPLY_TOPIC}")
        else:
            print(f"Subscription request failed: {result}")
    else:
        connected.clear()
        print(f"\nConnection rejected: {reason_code}")

    # Release the main program's connection wait.
    connection_response.set()


# Paho calls this when the broker confirms our subscription.
def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print("\nBroker rejected the reply subscription.")
    else:
        print(f"\nReply subscription confirmed: {REPLY_TOPIC}")


# Paho calls this when a message arrives on a subscribed topic.
def on_message(client, userdata, message):
    # Replace invalid text characters rather than crashing.
    payload = message.payload.decode("utf-8", errors="replace")

    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{GREEN}[{timestamp}] Reply on {message.topic}: {payload}{RESET}")

    # Restore the prompt after an incoming reply.
    print("Write your message here: ", end="", flush=True)


# Paho calls this when the client disconnects.
def on_disconnect(client, userdata, flags, reason_code, properties):
    connected.clear()
    print(f"\nDisconnected: {reason_code}")

    if reason_code != 0:
        print("Unexpected disconnection; MQTT will try to reconnect.")


# CREATE MQTT CLIENT 

def create_client():
    # VERSION2 selects the callback signatures used above.
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
    )

    # To use a broker that requires login, uncomment the line below
    # and replace the placeholders with your assigned credentials.
    # client.username_pw_set("YOUR_USERNAME", "YOUR_PASSWORD")

    # Keep it commented out for our current local anonymous broker.
    # Set credentials before calling connect() or connect_async().

    # Register the functions that handle MQTT events.
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Increase the reconnect delay from 1 second up to 10 seconds
    # if repeated reconnection attempts fail.
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    # No username/password is needed for our local anonymous broker.
    return client


#  SEND MESSAGE 

def publish_messages(client):
    while True:
        text = input("Write your message here: ").strip()

        # Typing quit stops the program.
        if text.lower() == "quit":
            break

        # Ignore empty messages.
        if not text:
            continue

        # Do not attempt a new send while disconnected.
        if not connected.is_set():
            print("Not connected. Wait for reconnection and try again.")
            continue

        # QoS 1 requests acknowledgement from the broker.
        # retain=False prevents this test message being saved
        # as the topic's retained message.
        result = client.publish(
            TOPIC,
            payload=text,
            qos=1,
            retain=False,
        )

        # First check whether Paho accepted the publish request.
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Publish request failed: {result.rc}")
            continue

        try:
            # The background MQTT thread handles the acknowledgement.
            result.wait_for_publish(timeout=TIMEOUT_SECONDS)

            if result.is_published():
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"{CYAN}[{timestamp}] SENT - Broker acknowledged{RESET}")
            else:
                # A timeout does not prove that delivery failed.
                print("No acknowledgement within 10 seconds; delivery uncertain.")

        except RuntimeError as error:
            print(f"Publish error: {error}")


# RUN AND CLEAN UP

def main():
    client = create_client()

    try:
        print(f"Connecting to {BROKER}:{PORT}...")

        # Begin connecting without blocking the main thread.
        client.connect_async(BROKER, PORT, keepalive=30)

        # Start a background thread for sending, receiving,
        # keepalive messages and automatic reconnection.
        client.loop_start()

        # Avoid waiting forever if the broker is unavailable.
        if not connection_response.wait(timeout=TIMEOUT_SECONDS):
            print("Connection timed out. Check that Mosquitto is running.")
            return

        if not connected.is_set():
            print("Connection was rejected. Check the broker configuration.")
            return

        print("Type a message and press Enter. Type quit to stop.")
        publish_messages(client)

    except (KeyboardInterrupt, EOFError):
        # Exit cleanly when Ctrl+C is pressed or terminal input closes.
        print("\nStopping publisher...")

    except OSError as error:
        print(f"Network error: {error}")

    finally:
        # Disconnect before stopping the background network thread.
        client.disconnect()
        client.loop_stop()
        print("Publisher stopped.")


# Run only when this file is executed directly.
if __name__ == "__main__":
    main()