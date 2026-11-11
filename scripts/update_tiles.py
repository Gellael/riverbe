"""
Skrip Generator Tile GEE Offline/Lokal
Mengambil token tile dari GEE dan menyimpannya ke frontend/public/gee_tiles.json dan frontend/src/gee_tiles.json
Kredensial dibaca otomatis dari backend/.env
"""
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import ee

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TILES_OUT_PUB = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "gee_tiles.json"
TILES_OUT_SRC = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "gee_tiles.json"

raw_key = os.getenv("GEE_SERVICE_ACCOUNT_JSON")
if not raw_key:
    key_file = Path(__file__).resolve().parent.parent / "gee-key.json"
    if key_file.exists():
        raw_key = key_file.read_text()
    else:
        raise ValueError("Variabel lingkungan 'GEE_SERVICE_ACCOUNT_JSON' tidak ditemukan di .env!")

info = json.loads(raw_key.strip())
PROJECT_ID = info["project_id"]

print(f"1. Menginisialisasi GEE untuk Project: {PROJECT_ID}...")
credentials = ee.ServiceAccountCredentials(info["client_email"], key_data=raw_key.strip())
ee.Initialize(credentials, project=PROJECT_ID)
print("✅ Terhubung ke Google Earth Engine")

YEAR_OLD = 2010
YEAR_NEW = 2020
ASSET_DIR = f"projects/{PROJECT_ID}/assets"

ASSET_2010     = f"{ASSET_DIR}/bibir_sungai_{YEAR_OLD}"
ASSET_2020     = f"{ASSET_DIR}/bibir_sungai_{YEAR_NEW}"
ASSET_DYN      = f"{ASSET_DIR}/dinamika_pergeseran_{YEAR_OLD}_{YEAR_NEW}"
ASSET_SAT_2010 = f"{ASSET_DIR}/citra_landsat_{YEAR_OLD}"
ASSET_SAT_2020 = f"{ASSET_DIR}/citra_landsat_{YEAR_NEW}"

def check_asset(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except Exception:
        return False

print(f"2. Memeriksa ketersediaan Asset GEE di {ASSET_DIR}...")
has_2010     = check_asset(ASSET_2010)
has_2020     = check_asset(ASSET_2020)
has_dyn      = check_asset(ASSET_DYN)
has_sat_2010 = check_asset(ASSET_SAT_2010)
has_sat_2020 = check_asset(ASSET_SAT_2020)

print(f"  - Bibir {YEAR_OLD}: {'Tersedia di Asset GEE ✅' if has_2010 else 'Belum selesai (menggunakan on-the-fly) ⚠️'}")
print(f"  - Bibir {YEAR_NEW}: {'Tersedia di Asset GEE ✅' if has_2020 else 'Belum selesai (menggunakan on-the-fly) ⚠️'}")
print(f"  - Dinamika: {'Tersedia di Asset GEE ✅' if has_dyn else 'Belum selesai (menggunakan on-the-fly) ⚠️'}")
print(f"  - Satelit {YEAR_OLD}: {'Tersedia di Asset GEE ✅' if has_sat_2010 else 'Belum selesai (menggunakan on-the-fly) ⚠️'}")
print(f"  - Satelit {YEAR_NEW}: {'Tersedia di Asset GEE ✅' if has_sat_2020 else 'Belum selesai (menggunakan on-the-fly) ⚠️'}")

indo_fc = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Indonesia"))
indo_mask = ee.Image.constant(1).clip(indo_fc).mask()

# --- 1. BIBIR SUNGAI 2010 ---
if has_2010:
    b2010_img = ee.Image(ASSET_2010).selfMask()
else:
    hydro = ee.Image("MERIT/Hydro/v1_0_1")
    corridor = hydro.select("upa").gte(30).focalMax(400, "circle", "meters").selfMask()
    jrc_2010 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_OLD)).first().select("waterClass")
    w2010 = jrc_2010.eq(3).updateMask(corridor).selfMask()
    b2010_img = w2010.unmask(0).focalMax(1, "square", "pixels").subtract(w2010.unmask(0).focalMin(1, "square", "pixels")).gt(0).selfMask()

map_2010 = ee.data.getMapId({"image": b2010_img.visualize(palette=["#fbbf24"], min=0, max=1)})

# --- 2. BIBIR SUNGAI 2020 ---
if has_2020:
    b2020_img = ee.Image(ASSET_2020).selfMask()
else:
    hydro = ee.Image("MERIT/Hydro/v1_0_1")
    corridor = hydro.select("upa").gte(30).focalMax(400, "circle", "meters").selfMask()
    jrc_2020 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_NEW)).first().select("waterClass")
    w2020 = jrc_2020.eq(3).updateMask(corridor).selfMask()
    b2020_img = w2020.unmask(0).focalMax(1, "square", "pixels").subtract(w2020.unmask(0).focalMin(1, "square", "pixels")).gt(0).selfMask()

map_2020 = ee.data.getMapId({"image": b2020_img.visualize(palette=["#ff2255"], min=0, max=1)})

# --- 3. DINAMIKA ---
if has_dyn:
    dyn_img = ee.Image(ASSET_DYN).selfMask()
else:
    hydro = ee.Image("MERIT/Hydro/v1_0_1")
    corridor = hydro.select("upa").gte(30).focalMax(400, "circle", "meters").selfMask()
    jrc_2010 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_OLD)).first().select("waterClass")
    jrc_2020 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", YEAR_NEW)).first().select("waterClass")
    w2010 = jrc_2010.eq(3).updateMask(corridor).selfMask()
    w2020 = jrc_2020.eq(3).updateMask(corridor).selfMask()
    erosi = w2020.unmask(0).And(w2010.unmask(0).Not()).selfMask()
    akresi = w2010.unmask(0).And(w2020.unmask(0).Not()).selfMask()
    dyn_img = ee.Image(0).byte().where(erosi, 1).where(akresi, 2).selfMask()

map_change = ee.data.getMapId({"image": dyn_img.visualize(bands=["dynamics"] if has_dyn else None, min=1, max=2, palette=["#ef4444", "#06b6d4"])})

# --- 4. SATELIT 2010 ---
if has_sat_2010:
    sat_2010_img = ee.Image(ASSET_SAT_2010)
    map_sat_2010 = ee.data.getMapId({"image": sat_2010_img})
else:
    l7_sr = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").filterDate("2009-01-01", "2011-12-31")
    def clean_l7(img):
        qa = img.select("QA_PIXEL")
        cloud = qa.bitwiseAnd(1 << 3).Or(qa.bitwiseAnd(1 << 4)).Or(qa.bitwiseAnd(1 << 1))
        rgb = img.select(["SR_B3", "SR_B2", "SR_B1"]).multiply(0.0000275).add(-0.2)
        return rgb.updateMask(cloud.eq(0))
    clean_2010 = l7_sr.map(clean_l7).median()
    raw_2010   = l7_sr.select(["SR_B3", "SR_B2", "SR_B1"]).median().multiply(0.0000275).add(-0.2)
    final_2010 = clean_2010.unmask(raw_2010).updateMask(indo_mask)
    map_sat_2010 = ee.data.getMapId({"image": final_2010.visualize(bands=["SR_B3", "SR_B2", "SR_B1"], min=0.03, max=0.25, gamma=1.3)})

# --- 5. SATELIT 2020 ---
if has_sat_2020:
    sat_2020_img = ee.Image(ASSET_SAT_2020)
    map_sat_2020 = ee.data.getMapId({"image": sat_2020_img})
else:
    l8_sr = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterDate("2019-06-01", "2021-06-30")
    def clean_l8(img):
        qa = img.select("QA_PIXEL")
        cloud = qa.bitwiseAnd(1 << 3).Or(qa.bitwiseAnd(1 << 4)).Or(qa.bitwiseAnd(1 << 1)).Or(qa.bitwiseAnd(1 << 2))
        rgb = img.select(["SR_B4", "SR_B3", "SR_B2"]).multiply(0.0000275).add(-0.2)
        return rgb.updateMask(cloud.eq(0))
    clean_2020 = l8_sr.map(clean_l8).median()
    raw_2020   = l8_sr.select(["SR_B4", "SR_B3", "SR_B2"]).median().multiply(0.0000275).add(-0.2)
    final_2020 = clean_2020.unmask(raw_2020).updateMask(indo_mask)
    map_sat_2020 = ee.data.getMapId({"image": final_2020.visualize(bands=["SR_B4", "SR_B3", "SR_B2"], min=0.03, max=0.25, gamma=1.3)})

output_data = {
    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "source": "Google Earth Engine Asset & L2 Surface Reflectance",
    "cloudQuality": "Minimal Cloud + Seamless Unmask",
    "assetsReady": {
        "bibir2010": has_2010,
        "bibir2020": has_2020,
        "dinamika": has_dyn,
        "satelit2010": has_sat_2010,
        "satelit2020": has_sat_2020,
    },
    "tile2010": map_2010["tile_fetcher"].url_format,
    "tile2020": map_2020["tile_fetcher"].url_format,
    "tileChange": map_change["tile_fetcher"].url_format,
    "tileSat2010": map_sat_2010["tile_fetcher"].url_format,
    "tileSat2020": map_sat_2020["tile_fetcher"].url_format,
}

for out_path in [TILES_OUT_PUB, TILES_OUT_SRC]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"✅ Berhasil menulis token tile ke: {out_path}")

print("🚀 Selesai!")

