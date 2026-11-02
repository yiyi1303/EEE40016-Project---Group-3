# Smart Grid MQTT Communication Prototype

This prototype tests two-way MQTT communication on one Windows computer.

The publisher sends text messages, the subscriber receives and sends manual replies, and Mosquitto forwards messages between them.


# Files

| File | Purpose |
| --- | --- |
| telemetry_publisher.py | Sends messages and receives replies |
| telemetry_subscriber.py | Receives messages and sends manual replies |
| mosquitto_local.conf | Configures the local MQTT broker |
| code_explanation.md | Explains the code and key MQTT concepts |


# Requirements 

1. Python with paho-mqtt installed
2. Mosquitto installed (64 bits - Window)
3. Three PowerShell terminals

** Install the Python dependency if needed **
py -m pip install "paho-mqtt>=2.1,<3"


# Broker configuration

conf 
listener [1024 < port number < 65535] [IPv4 Address via ipconfig]
allow_anonymous true

allow_anonymous false only when required client.username_pw_set("YOUR_USERNAME", "YOUR_PASSWORD")


# Run the prototype

Open three terminals ( single for mosquitto_local.conf and split for publisher and subscriber)

Make sure they all in the same folder

** Terminal 1: broker ** 
& "C:\Program Files\mosquitto\mosquitto.exe" -c ".\mosquitto_local.conf" -v

leave it running 

** Terminal 2: subscriber **
py telemetry_subscriber.py

wait for "Telemetry subscription confirmed: smartgrid_mqtt_test"

** Terminal 3: publisher **
py telemetry_publisher.py

wait for the reply subscription to be confirmed


# How about between 2 laptops? - Sure

| Your laptop | Their laptop |
| --- | ---- |
| Runs Mosquitto using mosquitto_local.conf | Does not run Mosquitto |
| Runs the subscriber | Runs the publisher |
| Connects to [1024 < port number < 65535]:[IPv4 Address via ipconfig] | Connects to your [1024 < port number < 65535]:[IPv4 Address via ipconfig] | 

You can swap publisher/subcriber roles


# Test communication

1. From publisher, greet the subscriber by simply type "hi"
2. Confirm "hi" appears in the subscriber 
3. In subscriber, reply with any message such as "how you doing?"
4. Confirm the reply appears in the publisher.

Broker acknowledgement confirms receipt by the broker


# Stop the prototype

Type "quit" in both Python terminals and press Ctrl+C in the broker terminal


# Troubleshooting

| Issue | Check |
| --- | --- |
| Connection timeout | Broker is running; both programs use [1024 < port number < 65535] [IPv4 Address via ipconfig] | 
| Not authorized | Correct broker configuration loaded; username_pw_set is disabled |
| Connected but no messages | Topics match; subscription confirmed before sending |
|Client repeatedly disconnects | Publisher and subscriber have different clients IDs |
| Cannot open configuration | Terminal is in the project folder; filename ends in .conf |


# Current scope

This version exchanges manually typed text messages

It does not yet validate grid measurements, detect stale telemetry, inject delay or message loss, or control EV charging

The next stage will be structured JSON telemetry with agreed units, measurement timestamps, session IDs and sequence number