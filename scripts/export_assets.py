"""
Skrip Ekspor Asset Google Earth Engine (GEE) Resmi untuk Indonesia
Semua kredensial dibaca otomatis dari backend/.env tanpa hardcode project ID.
"""
import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import ee

# Load .env dari root backend
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

raw_key = os.getenv("GEE_SERVICE_ACCOUNT_JSON")
if not raw_key:
    # Cek apakah ada file gee-key.json lokal
    key_file = Path(__file__).resolve().parent.parent / "gee-key.json"
    if key_file.exists():
        raw_key = key_file.read_text()
    else:
        raise ValueError("Variabel lingkungan 'GEE_SERVICE_ACCOUNT_JSON' tidak ditemukan di .env!")

info = json.loads(raw_key.strip())
PROJECT_ID = info["project_id"]

credentials = ee.ServiceAccountCredentials(info["client_email"], key_data=raw_key.strip())
ee.Initialize(credentials, project=PROJECT_ID)
print(f"✅ Terhubung ke Google Earth Engine (Project: {PROJECT_ID})")

YEAR_OLD = 2010
YEAR_NEW = 2020

print("1. Menyiapkan batas daratan Indonesia dan lapisan citra satelit & alur sungai...")
indo_fc = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Indonesia"))
indo_mask = ee.Image.constant(1).clip(indo_fc).mask()
indo_geom = ee.Geometry.Rectangle([94.5, -11.5, 141.5, 6.5], None, False)

# --- 1. Citra Satelit Landsat 2010 True Color ---
l7_2010 = ee.ImageCollection("LANDSAT/LE07/C02/T1").filterDate("2009-06-01", "2011-06-30")
comp_2010 = ee.Algorithms.Landsat.simpleComposite(collection=l7_2010, asFloat=True)
sat_2010_rgb = comp_2010.select(["B3", "B2", "B1"]).multiply(255).byte().clip(indo_fc)

# --- 2. Jaringan Sungai MERIT Hydro ---
hydro = ee.Image("MERIT/Hydro/v1_0_1")
land_drainage = hydro.select("dir").mask().And(hydro.select("elv").gte(1))
river_net = hydro.select("upa").gte(30).selfMask()
corridor = river_net.focalMax(400, "circle", "meters").updateMask(indo_mask).updateMask(land_drainage).selfMask()

# Air Permanen (waterClass == 3)
jrc_2010 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_OLD)).first().select("waterClass")
jrc_2020 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_NEW)).first().select("waterClass")

w2010 = jrc_2010.eq(3).updateMask(corridor).selfMask()
w2020 = jrc_2020.eq(3).updateMask(corridor).selfMask()

# Garis bibir tebing sungai
b2010 = w2010.unmask(0).focalMax(1, "square", "pixels").subtract(w2010.unmask(0).focalMin(1, "square", "pixels")).gt(0).byte().rename("bank_2010")
b2020 = w2020.unmask(0).focalMax(1, "square", "pixels").subtract(w2020.unmask(0).focalMin(1, "square", "pixels")).gt(0).byte().rename("bank_2020")

# Dinamika
erosi = w2020.unmask(0).And(w2010.unmask(0).Not())
akresi = w2010.unmask(0).And(w2020.unmask(0).Not())
change_img = ee.Image(0).byte().where(erosi, 1).where(akresi, 2).rename("dynamics")

project_assets = f"projects/{PROJECT_ID}/assets"

tasks = [
    {
        "desc": f"Ekspor_Citra_Landsat_{YEAR_OLD}",
        "asset_id": f"{project_assets}/citra_landsat_{YEAR_OLD}",
        "image": sat_2010_rgb,
        "scale": 60,
    },
    {
        "desc": f"Ekspor_Bibir_{YEAR_OLD}",
        "asset_id": f"{project_assets}/bibir_sungai_{YEAR_OLD}",
        "image": b2010.selfMask(),
        "scale": 30,
    },
    {
        "desc": f"Ekspor_Bibir_{YEAR_NEW}",
        "asset_id": f"{project_assets}/bibir_sungai_{YEAR_NEW}",
        "image": b2020.selfMask(),
        "scale": 30,
    },
    {
        "desc": f"Ekspor_Dinamika_{YEAR_OLD}_{YEAR_NEW}",
        "asset_id": f"{project_assets}/dinamika_pergeseran_{YEAR_OLD}_{YEAR_NEW}",
        "image": change_img.selfMask(),
        "scale": 30,
    }
]

print("\n2. Memeriksa daftar tugas ekspor:")
for t in tasks:
    print(f"  - {t['desc']} -> {t['asset_id']} (Resolusi: {t['scale']}m)")

if len(sys.argv) > 1 and sys.argv[1] == "--start":
    print("\n🚀 Memulai pengiriman tugas ke GEE Server...")
    for t in tasks:
        task = ee.batch.Export.image.toAsset(
            image=t["image"],
            description=t["desc"],
            assetId=t["asset_id"],
            region=indo_geom,
            scale=t["scale"],
            maxPixels=1e13
        )
        task.start()
        print(f"  ✅ Tugas '{t['desc']}' dikirim (ID: {task.id})")
    print("\nSemua tugas berhasil dikirim ke server GEE!")
else:
    print("\nℹ️ Gunakan 'python export_assets.py --start' untuk memulai ekspor ke GEE Asset.")

