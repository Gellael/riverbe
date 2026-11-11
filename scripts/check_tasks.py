"""
Skrip Cek Status Tugas Google Earth Engine (GEE)
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
print(f"🔐 Terhubung ke Google Earth Engine (Project: {PROJECT_ID})")

print("\n📋 Mengambil daftar tugas terbaru dari server GEE...")
print("=" * 60)

tasks = ee.batch.Task.list()
if not tasks:
    print("Tidak ada tugas di antrean GEE.")
else:
    for i, t in enumerate(tasks[:15], 1):
        status = t.state
        status_icon = "⏳"
        if status == "COMPLETED":
            status_icon = "✅"
        elif status == "RUNNING":
            status_icon = "🔄"
        elif status == "FAILED":
            status_icon = "❌"
        elif status == "CANCELLED":
            status_icon = "🚫"
            
        desc = t.config.get("description", "Tanpa Deskripsi")
        task_type = t.task_type
        print(f"{status_icon} [{i}] {desc}")
        print(f"   Status   : {status}")
        print(f"   Tipe     : {task_type}")
        if status == "FAILED":
            print(f"   ⛔ Error  : {t.status().get('error_message')}")
        print("-" * 60)

