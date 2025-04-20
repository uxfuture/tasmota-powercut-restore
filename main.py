import os
import json
import threading
import time
from datetime import datetime
import pytz
import paho.mqtt.client as mqtt
from prometheus_client import Gauge, start_http_server

# ENV
TOPIC = os.getenv("TASMOTA_TOPIC", "tasmota_E2E13F")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

# Timezone setup
local_tz = pytz.timezone("Asia/Kolkata")
now = datetime.now(local_tz)
last_update = datetime.now()

# Prometheus gauge for corrected energy today
corrected = Gauge("tasmota_energy_today_corrected", "Corrected ENERGY.Today")
start_http_server(9500)
print("🚀 /metrics exposed on :9500")

# Persistent state for energy tracking
state = {
    "carry": 0.0,
    "last": 0.0,
    "apply_correction": False
}

# MQTT message handler
def on_message(client, userdata, msg):
    global state
    global last_update

    last_update = datetime.now()
    try:
        payload = json.loads(msg.payload.decode())
        if "ENERGY" not in payload:
            print("⚠️ No ENERGY data in payload:", payload)
            return

        today = payload["ENERGY"].get("Today", 0.0)
        hour_now = now.hour

        # Adjust for small starting wattage values
        if abs(today) <= 1e-2 and hour_now != 0:
            if (state["last"] - today > 0 and not state["apply_correction"]):
                state["carry"] = state["carry"] + state["last"]
                state["apply_correction"] = True
                print(f"⚡ Reset detected. Carrying over {state['carry']}, Full Power: {repr(today)}")
            elif state["apply_correction"]:
                corrected_today = (state["carry"] + today)
                corrected.set(corrected_today)

                state["apply_correction"] = False
            else:
                corrected_today = (state["carry"] + today)
                corrected.set(corrected_today)

                print(f"{state['last'] - corrected_today} is less than zero ...")
                print(f"📦 today={today}, corrected={corrected_today}, carry={state['carry']}, last={state['last']}")
        else:
            corrected_today = (state["carry"] + today)
            corrected.set(corrected_today)

            print("Last Value Saved")
            print(f"✅ Normal tracking: {repr(today)}")
            print(f"✅ Corrected tracking: {repr(corrected_today)}")

        state["last"] = today
        # At midnight, reset everything
        if hour_now == 0:
            print("🕛 Midnight: resetting correction state")
            state = {"carry": 0.0, "last": today}
            corrected_today = 0

    except Exception as e:
        print("💥 Error in message handler:", e)

# MQTT setup
client = mqtt.Client()
if MQTT_USER and MQTT_PASS:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.subscribe(f"tele/{TOPIC}/SENSOR")

client.loop_forever()

# [ TODO ] Keepalive loop to rebroadcast last corrected value if no MQTT for 60 seconds
# def keepalive_loop():
#     while True:
#         if (datetime.now() - last_update) > timedelta(seconds=60):
#             corrected.set(state["last"] + state["carry"])
#             print("🔄 No MQTT — rebroadcasting last corrected value to avoid gap.")
#         time.sleep(30)

# # Start keepalive loop in a daemon thread
# threading.Thread(target=keepalive_loop, daemon=True).start()

