import os
import time
import json
import requests
from datetime import datetime
import paho.mqtt.publish as publish

PROMETHEUS_URL = os.environ.get("PROM_URL", "http://prometheus:9090")
TOPIC = os.environ.get("TASMOTA_TOPIC", "tasmota_E2E13F")
MQTT_BROKER = os.environ.get("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASS = os.environ.get("MQTT_PASS")

STATE_FILE = "/data/last_energy.json"


auth = None
if MQTT_USER is not None:
    auth = {"username": MQTT_USER}
if MQTT_PASS is not None:
    auth["password"] = MQTT_PASS


def query_prometheus(metric):
    query = f'{metric}{{status_topic="{TOPIC}"}}'
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    result = resp.json()["data"]["result"]
    return float(result[0]["value"][1]) if result else None

def load_last_energy():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"total": 0, "today": 0}

def save_last_energy(total, today):
    with open(STATE_FILE, "w") as f:
        json.dump({"total": total, "today": today}, f)

def send_energy_total_correction(new_total):
    payload = str(round(new_total, 3))
    print(f"Sending corrected EnergyTotal: {payload}")
    publish.single(
        topic=f"cmnd/{TOPIC}/EnergyTotal",
        payload=payload,
        hostname=MQTT_BROKER,
        port=MQTT_PORT,
        auth=auth
    )

while True:
    now = datetime.now()
    in_reset_window = now.hour == 0 and now.minute < 30

    today = query_prometheus("tasmota_energy_today")
    total = query_prometheus("tasmota_energy_total")

    if today is None or total is None:
        print("No data yet. Waiting...")
        time.sleep(60)
        continue

    last = load_last_energy()

    if not in_reset_window and today == 0 and last["today"] > 0:
        print("Power cut reset detected — Restoring Saved Total...")
        corrected_total = total + last["today"]
        send_energy_total_correction(corrected_total)
    else:
        save_last_energy(total, today)

    time.sleep(60)
