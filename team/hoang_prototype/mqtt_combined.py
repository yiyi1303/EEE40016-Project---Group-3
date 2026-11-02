"""Two-way MQTT chat - one terminal per laptop.
 
Laptop A: py mqtt_chat.py a
Laptop B: py mqtt_chat.py b --broker <laptop A Wi-Fi IPv4>
 
Each side publishes to its own topic and subscribes to the other side's topic.
"""
import argparse
import os
import threading
from datetime import datetime
 
from paho.mqtt import client as mqtt
 
# Enables ANSI colours in Windows Command Prompt.
os.system("")
 
GREEN = "\033[92m"   # Incoming messages.
CYAN = "\033[96m"    # Outgoing messages acknowledged by the broker.
RESET = "\033[0m"
 
BASE_TOPIC = "smartgrid_mqtt_test"
TIMEOUT_SECONDS = 10
 
parser = argparse.ArgumentParser()
parser.add_argument("role", choices=["a", "b"], help="this laptop's role")
parser.add_argument("--broker", default="A's IPv4", help="broker IPv4 address")
parser.add_argument("--port", type=int, default=1884, help="broker port")
args = parser.parse_args()
 
PEER = "b" if args.role == "a" else "a"
SEND_TOPIC = f"{BASE_TOPIC}/{args.role}"   # publish here
RECV_TOPIC = f"{BASE_TOPIC}/{PEER}"        # listen here
CLIENT_ID = f"smartgrid-{args.role}"       # must differ between laptops
 
connected = threading.Event()
connection_response = threading.Event()
 
 
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connected.set()
        print("\nConnected to MQTT broker!")
        # Subscribe after every (re)connection.
        client.subscribe(RECV_TOPIC, qos=1)
    else:
        connected.clear()
        print(f"\nConnection rejected: {reason_code}")
    connection_response.set()
 
 
def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print("\nBroker rejected the subscription.")
    else:
        print(f"\nSubscription confirmed: {RECV_TOPIC}. Ready to chat.")
        print("You: ", end="", flush=True)
 
 
def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8", errors="replace")
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{GREEN}[{timestamp}] {PEER.upper()}: {payload}{RESET}")
    print("You: ", end="", flush=True)
 
 
def on_disconnect(client, userdata, flags, reason_code, properties):
    connected.clear()
    print(f"\nDisconnected: {reason_code}")
    if reason_code != 0:
        print("Unexpected disconnection; MQTT will try to reconnect.")
 
 
def create_client():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
    )
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    return client
 
 
def send_messages(client):
    while True:
        text = input("You: ").strip()
 
        if text.lower() == "quit":
            break
        if not text:
            continue
        if not connected.is_set():
            print("Not connected. Wait for reconnection and try again.")
            continue
 
        result = client.publish(SEND_TOPIC, payload=text, qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Publish request failed: {result.rc}")
            continue
 
        try:
            result.wait_for_publish(timeout=TIMEOUT_SECONDS)
            if result.is_published():
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"{CYAN}[{timestamp}] SENT - Broker acknowledged{RESET}")
            else:
                print("No acknowledgement within 10 seconds; delivery uncertain.")
        except RuntimeError as error:
            print(f"Publish error: {error}")
 
 
def main():
    client = create_client()
 
    try:
        print(f"Role {args.role.upper()}: connecting to {args.broker}:{args.port}...")
        client.connect_async(args.broker, args.port, keepalive=30)
        client.loop_start()
 
        if not connection_response.wait(timeout=TIMEOUT_SECONDS):
            print("Connection timed out. Check the broker is running and the IP is correct.")
            return
        if not connected.is_set():
            print("Connection was rejected. Check the broker configuration.")
            return
 
        print("Type a message and press Enter. Type quit to stop.")
        send_messages(client)
 
    except (KeyboardInterrupt, EOFError):
        print("\nStopping...")
    except OSError as error:
        print(f"Network error: {error}")
    finally:
        client.disconnect()
        client.loop_stop()
        print("Stopped.")
 
 
if __name__ == "__main__":
    main()