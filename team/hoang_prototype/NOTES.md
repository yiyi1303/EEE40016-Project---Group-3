# Hoang's MQTT prototype: what it is and how it fits

These are Hoang's files as sent on 12 October 2026, with the small changes listed at the
end. The originals are unchanged in Munir's Downloads folder.

## What it does

A two-way MQTT chat: `telemetry_publisher.py` sends typed messages, `telemetry_subscriber.py`
receives them and sends typed replies, and a broker passes them on. It shows the pieces the
project's messaging is built from: connecting, subscribing, QoS 1 acknowledgements,
reconnecting, and separate client IDs. It works, tested against the laptop's broker:
"hi" went one way and the reply came back.

## How it fits the project

Hoang's readme names the next stage as "structured JSON telemetry with agreed units,
measurement timestamps, session IDs and sequence numbers". That part already exists in the
project and is shared by everyone: `src/messages.py` defines every message (JSON, units,
simulated timestamps, sequence numbers, a validator), and `src/mqtt_edge.py` carries them
between the laptop and the Raspberry Pi. So the chat itself is not part of a run.

What the study still needs from Hoang is the comms node itself: the delay and loss
injector and the trust score, as the class in `team/hoang_link.py`. It runs inside the twin
on the laptop, so it needs no MQTT of its own, and it is checked by V5 and V6:

    py tests/test_node_acceptance.py --team hoang

The chat is still useful as a quick check that two devices can reach each other over MQTT,
before a real run. With the project's broker running on the laptop (`py tools/broker.py`,
port 1883):

    on the laptop:  py telemetry_subscriber.py 127.0.0.1 1883
    on the Pi:      python3 telemetry_publisher.py <laptop address> 1883

(The Pi needs paho-mqtt for this: `sudo apt install python3-paho-mqtt`. The project's own
Pi programs carry their own copy and need nothing.)

## Changes made

- `mosquitto_local.conf.txt` renamed to `mosquitto_local.conf`. Windows had added `.txt`, so
  the readme's broker command would have stopped with "Cannot open configuration" (the
  last row of Hoang's own troubleshooting table).
- Both scripts take the broker address and port on the command line, as above, so they can
  run between two devices without editing the file. Without arguments they behave exactly
  as before (127.0.0.1, port 1884).
- Typos in `readme.md` corrected: subscriber file name, Mosquitto, replies, publisher,
  subscription, stale. `code_explanation.md`, listed in the readme, was not among the
  files sent.
