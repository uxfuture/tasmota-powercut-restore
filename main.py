import os
import json
import threading
import time
from datetime import datetime, timedelta
import pytz
import paho.mqtt.client as mqtt
from prometheus_client import Gauge, start_http_server

# ENV
TOPIC = os.getenv("TASMOTA_TOPIC", "tasmota_E2E13F")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

STATE_PATH = "/data/state.json"

def load_state():
    try:
        with open(STATE_PATH, "r") as f:
            state = json.load(f)
            print(f"📥 Loaded state from disk: {state}")
            return state
    except (FileNotFoundError, json.JSONDecodeError):
        print("🆕 No previous state found — starting fresh")
        return {
            "carry": 0.0,
            "last": 0.0,
            "apply_correction": False
        }

def save_state(state):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
        print(f"💾 State saved: {state}")
    except Exception as e:
        print("💥 Error saving state:", e)

# Initial state load
state = load_state()

# Timezone setup
local_tz = pytz.timezone("Asia/Kolkata")

# Prometheus setup
corrected = Gauge("tasmota_energy_today_corrected", "Corrected ENERGY.Today")
start_http_server(9500)
print("🚀 /metrics exposed on :9500")

# Last update tracker for keepalive loop
last_update = datetime.now(local_tz)

# MQTT message handler
def on_message(client, userdata, msg):
    global state, last_update

    now = datetime.now(local_tz)
    last_update = now
    hour_now = now.hour

    try:
        payload = json.loads(msg.payload.decode())
        if "ENERGY" not in payload:
            print("⚠️ No ENERGY data in payload:", payload)
            return

        today = payload["ENERGY"].get("Today", 0.0)

        # Reset logic for powercuts
        if abs(today) <= 1e-2 and hour_now != 0:
            if (state["last"] - today > 0 and not state["apply_correction"]):
                state["carry"] += state["last"]
                state["apply_correction"] = True
                print(f"⚡ Reset detected. Carrying over {state['carry']}, Full Power: {repr(today)}")
            elif state["apply_correction"]:
                corrected_today = state["carry"] + today
                corrected.set(corrected_today)
                state["apply_correction"] = False
            else:
                corrected_today = state["carry"] + today
                corrected.set(corrected_today)
                print(f"{state['last'] - corrected_today} is less than zero ...")
                print(f"📦 today={today}, corrected={corrected_today}, carry={state['carry']}, last={state['last']}")
        else:
            corrected_today = state["carry"] + today
            corrected.set(corrected_today)
            print(f"✅ Normal tracking, Time is {hour_now}")
            print(f"📈 Raw today: {today}")
            print(f"✅ Corrected: {corrected_today}")

        # Save raw reading
        state["last"] = today

        # Midnight reset
        if hour_now == 0:
            print("🕛 Midnight: resetting correction state")
            state["carry"] = 0.0
            state["apply_correction"] = False

        save_state(state)

    except Exception as e:
        print("💥 Error in message handler:", e)

# MQTT setup
client = mqtt.Client()
if MQTT_USER and MQTT_PASS:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.subscribe(f"tele/{TOPIC}/SENSOR")

# # Keepalive loop: rebroadcasts last value if MQTT silent
# def keepalive_loop():
#     global last_update
#     while True:
#         now = datetime.now(local_tz)
#         if (now - last_update) > timedelta(seconds=60):
#             corrected_value = state["carry"] + state["last"]
#             corrected.set(corrected_value)
#             print("🔄 No MQTT — rebroadcasting last corrected value:", corrected_value)
#         time.sleep(30)

# # Start keepalive loop in background
# threading.Thread(target=keepalive_loop, daemon=True).start()

# Start MQTT loop
client.loop_forever()
