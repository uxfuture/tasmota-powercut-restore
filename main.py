import os, datetime
import paho.mqtt.client as mqtt
import json
from prometheus_client import Gauge, start_http_server


# PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")
TOPIC = os.getenv("TASMOTA_TOPIC", "tasmota_E2E13F")
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

corrected = Gauge("tasmota_energy_today_corrected", "Corrected ENERGY.Today")
state = {"carry": 0.0, "last": 0.0, "active": False}

def on_connect():
    print("Connected to MQTT successfully")
def on_connect_fail():
    print("Connect to MQTT failed")
def on_message(client, userdata, msg):
    global state
    payload = json.loads(msg.payload.decode())
    if "ENERGY" not in payload:
        print("There's no energy in payload", payload)
        return

    today = payload["ENERGY"].get("Today", 0.0)
    now_hour = datetime.now().hour

    if today == 0 and now_hour != 0:
        if not state["active"]:
            state["carry"] = state["last"]
            state["active"] = True
    elif today > 0 and state["active"]:
        corrected.set(today + state["carry"])
        state = {"carry": 0.0, "last": today, "active": False}
    else:
        corrected.set(today)
        print("Correcting Data?")
        state["last"] = today

client = mqtt.Client()
if MQTT_USER and MQTT_PASS is not None:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.on_connect = on_connect
client.on_connect_fail = on_connect_fail
client.subscribe(f"tele/{TOPIC}/SENSOR")
start_http_server(9500)

client.loop_forever()
