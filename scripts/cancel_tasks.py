"""
Skrip Pembatal Tugas Duplikat GEE (Hanya membatalkan status READY)
Kredensial dibaca otomatis dari backend/.env
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import ee

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

raw_key = os.getenv("GEE_SERVICE_ACCOUNT_JSON")
if not raw_key:
    key_file = Path(__file__).resolve().parent.parent / "gee-key.json"
    if key_file.exists():
        raw_key = key_file.read_text()
    else:
        raise ValueError("Variabel lingkungan 'GEE_SERVICE_ACCOUNT_JSON' tidak ditemukan di .env!")

info = json.loads(raw_key.strip())
PROJECT_ID = info["project_id"]

credentials = ee.ServiceAccountCredentials(info["client_email"], key_data=raw_key.strip())
ee.Initialize(credentials, project=PROJECT_ID)
print(f"🔐 Terhubung ke GEE (Project: {PROJECT_ID})")

n = 0
for t in ee.batch.Task.list():
    desc = str(t.config.get("description", ""))
    # Hanya batalkan jika status READY dan merupakan duplikat
    if t.state == "READY":
        print(f"Membatalkan tugas READY: {desc} (ID: {t.id})")
        ee.data.cancelTask(t.id)
        n += 1

print(f"✅ Selesai. Total tugas READY yang dibatalkan: {n}")

