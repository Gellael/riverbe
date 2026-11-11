"""
Skrip Generator Tile GEE Offline/Lokal
Mengambil token tile dari GEE dan menyimpannya ke backend/gee_tiles.json
Menggunakan Asset GEE jika sudah selesai diekspor, atau komposit cepat (simpleComposite) jika masih diproses.
"""
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import ee

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TILES_OUT_BE = Path(__file__).resolve().parent.parent / "gee_tiles.json"
TILES_OUT_PUB = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "gee_tiles.json"

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
print(f"  - Satelit {YEAR_OLD}: {'Tersedia di Asset GEE ✅' if has_sat_2010 else 'Belum selesai (menggunakan fast composite) ⚠️'}")
print(f"  - Satelit {YEAR_NEW}: {'Tersedia di Asset GEE ✅' if has_sat_2020 else 'Belum selesai (menggunakan fast composite) ⚠️'}")

indo_fc = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Indonesia"))
indo_mask = ee.Image.constant(1).clip(indo_fc).mask()

# --- 1. BIBIR SUNGAI 2010 ---
print("  - Menyiapkan layer Bibir 2010...")
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
print("  - Menyiapkan layer Bibir 2020...")
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
print("  - Menyiapkan layer Dinamika...")
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
print("  - Menyiapkan layer Satelit 2010...")
if has_sat_2010:
    sat_2010_img = ee.Image(ASSET_SAT_2010)
    map_sat_2010 = ee.data.getMapId({"image": sat_2010_img})
else:
    l7 = ee.ImageCollection("LANDSAT/LE07/C02/T1").filterDate("2009-06-01", "2011-06-30")
    comp_2010 = ee.Algorithms.Landsat.simpleComposite(collection=l7, asFloat=True)
    vis_2010 = comp_2010.select(["B3", "B2", "B1"]).clip(indo_fc)
    map_sat_2010 = ee.data.getMapId({"image": vis_2010.visualize(bands=["B3", "B2", "B1"], min=0.03, max=0.25, gamma=1.3)})

# --- 5. SATELIT 2020 ---
print("  - Menyiapkan layer Satelit 2020...")
if has_sat_2020:
    sat_2020_img = ee.Image(ASSET_SAT_2020)
    map_sat_2020 = ee.data.getMapId({"image": sat_2020_img})
else:
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1").filterDate("2019-06-01", "2021-06-30")
    comp_2020 = ee.Algorithms.Landsat.simpleComposite(collection=l8, asFloat=True)
    vis_2020 = comp_2020.select(["B4", "B3", "B2"]).clip(indo_fc)
    map_sat_2020 = ee.data.getMapId({"image": vis_2020.visualize(bands=["B4", "B3", "B2"], min=0.04, max=0.25, gamma=1.2)})

output_data = {
    "status": "ready",
    "source": "Google Earth Engine Asset & L2 Surface Reflectance",
    "scope": "Indonesia Only (Lingkup Indonesia Saja)",
    "cloudQuality": "Minimal Cloud + Seamless Unmask",
    "yearOld": YEAR_OLD,
    "yearNew": YEAR_NEW,
    "asset2010": ASSET_2010 if has_2010 else None,
    "asset2020": ASSET_2020 if has_2020 else None,
    "assetDynamics": ASSET_DYN if has_dyn else None,
    "assetSat2010": ASSET_SAT_2010 if has_sat_2010 else None,
    "assetSat2020": ASSET_SAT_2020 if has_sat_2020 else None,
    "tile2010": map_2010["tile_fetcher"].url_format,
    "tile2020": map_2020["tile_fetcher"].url_format,
    "tileChange": map_change["tile_fetcher"].url_format,
    "tileSat2010": map_sat_2010["tile_fetcher"].url_format,
    "tileSat2020": map_sat_2020["tile_fetcher"].url_format,
    "colors": {
        "bank2010": "#fbbf24",
        "bank2020": "#ff2255",
        "erosi": "#ef4444",
        "akresi": "#06b6d4"
    }
}

for out_path in [TILES_OUT_BE, TILES_OUT_PUB]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"✅ Berhasil menulis token tile ke: {out_path}")

print("🚀 Selesai memperbarui token tile!")
