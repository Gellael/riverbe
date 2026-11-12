"""
Generator Garis Bibir Sungai Indonesia (GEE Assets + Hydro Adaptive)
Mengekstrak batas pinggir sungai (tebing kiri dan kanan) untuk SELURUH sungai di Indonesia (2010 vs 2020).
Menjamin seluruh sungai (termasuk Bengkulu, Asahan, dll) memiliki batas tepi pinggir sungai yang tampak jelas.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import ee

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

RIVERS_PATH = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "rivers.json"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "rivers"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_ALL_BE = Path(__file__).resolve().parent.parent / "gee_tiles_rivers.json"
OUT_ALL_FE = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "gee_tiles_rivers.json"
OUT_MAIN_BE = Path(__file__).resolve().parent.parent / "gee_tiles.json"
OUT_MAIN_FE = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "gee_tiles.json"

raw_key = os.getenv("GEE_SERVICE_ACCOUNT_JSON")
if not raw_key:
    key_file = Path(__file__).resolve().parent.parent / "gee-key.json"
    if key_file.exists():
        raw_key = key_file.read_text()
    else:
        raise ValueError("Variabel lingkungan 'GEE_SERVICE_ACCOUNT_JSON' tidak ditemukan!")

info = json.loads(raw_key.strip())
PROJECT_ID = info["project_id"]

print(f"1. Menginisialisasi GEE untuk Project: {PROJECT_ID}...")
credentials = ee.ServiceAccountCredentials(info["client_email"], key_data=raw_key.strip())
ee.Initialize(credentials, project=PROJECT_ID)
print("✅ Terhubung ke Google Earth Engine")

# Asset resmi yang sudah diekspor
ASSET_DIR = f"projects/{PROJECT_ID}/assets"
ASSET_2010 = f"{ASSET_DIR}/bibir_sungai_2010"
ASSET_2020 = f"{ASSET_DIR}/bibir_sungai_2020"
ASSET_DYN  = f"{ASSET_DIR}/dinamika_pergeseran_2010_2020"
ASSET_SAT_2010 = f"{ASSET_DIR}/citra_landsat_2010"
ASSET_SAT_2020 = f"{ASSET_DIR}/citra_landsat_2020"

b2010_asset = ee.Image(ASSET_2010)
b2020_asset = ee.Image(ASSET_2020)
dyn_asset   = ee.Image(ASSET_DYN)

# Mask daratan Indonesia resmi
indo_fc = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Indonesia"))
indo_mask = ee.Image.constant(1).clip(indo_fc).mask()

# Basemap satelit nasional
map_sat_2010 = ee.data.getMapId({"image": ee.Image(ASSET_SAT_2010)})
map_sat_2020 = ee.data.getMapId({"image": ee.Image(ASSET_SAT_2020)})

# Dataset Hidrologi Nasional MERIT Hydro & JRC Water
hydro = ee.Image("MERIT/Hydro/v1_0_1")
land_drainage = hydro.select("dir").mask().And(hydro.select("elv").gte(1))

# upa >= 3 km² agar mencakup seluruh alur sungai kecil dan sedang di Indonesia
river_net = hydro.select("upa").gte(3).updateMask(land_drainage).updateMask(indo_mask).selfMask()

jrc_2010 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", 2010)).first().select("waterClass")
jrc_2020 = ee.ImageCollection("JRC/GSW1_4/YearlyHistory").filter(ee.Filter.eq("year", 2020)).first().select("waterClass")

# Koridor sungai
corridor = river_net.focalMax(250, "circle", "meters").updateMask(indo_mask).selfMask()

# Badan air: gabungan deteksi air satelit (permanen + musiman >= 2) dan lebar alur hidrologis
w10_sat = jrc_2010.gte(2).updateMask(corridor)
w20_sat = jrc_2020.gte(2).updateMask(corridor)

stream_channel_2010 = river_net.focalMax(45, "circle", "meters")
stream_channel_2020 = river_net.focalMax(55, "circle", "meters")

water_2010_full = w10_sat.unmask(0).Or(stream_channel_2010).updateMask(indo_mask).selfMask()
water_2020_full = w20_sat.unmask(0).Or(stream_channel_2020).updateMask(indo_mask).selfMask()

# Garis tepi bibir sungai (Outer banklines: Left & Right Banks)
bank_2010_full = water_2010_full.unmask(0).focalMax(1, "square", "pixels") \
    .subtract(water_2010_full.unmask(0).focalMin(1, "square", "pixels")).gt(0) \
    .Or(b2010_asset.unmask(0).gt(0)).updateMask(indo_mask).selfMask()

bank_2020_full = water_2020_full.unmask(0).focalMax(1, "square", "pixels") \
    .subtract(water_2020_full.unmask(0).focalMin(1, "square", "pixels")).gt(0) \
    .Or(b2020_asset.unmask(0).gt(0)).updateMask(indo_mask).selfMask()

# Dinamika: erosi (merah) & akresi (cyan)
erosi_full = water_2020_full.unmask(0).And(water_2010_full.unmask(0).Not()).selfMask()
akresi_full = water_2010_full.unmask(0).And(water_2020_full.unmask(0).Not()).selfMask()
dyn_full = ee.Image(0).byte().where(erosi_full, 1).where(akresi_full, 2).Or(dyn_asset.unmask(0)).updateMask(indo_mask).selfMask()

# Baca daftar sungai
rivers = json.loads(RIVERS_PATH.read_text())
print(f"2. Memproses garis batas pinggir sungai untuk {len(rivers)} sungai se-Indonesia...")

all_rivers_tiles = {}

for r in rivers:
    r_id = r["id"]
    r_name = r["name"]
    bounds = r["bounds"]
    min_lon, min_lat = bounds[0]
    max_lon, max_lat = bounds[1]
    
    # Margin 0.05 derajat (~5 km) di sekitar bounding box sungai
    margin = 0.05
    geom = ee.Geometry.Rectangle([min_lon - margin, min_lat - margin, max_lon + margin, max_lat + margin], None, False)
    
    print(f"  🌊 Menghasilkan batas pinggir {r_name} ({r_id})...")
    
    # Clip HANYA ke bounding box sungai & mask daratan Indonesia
    r_b2010 = bank_2010_full.clip(geom).selfMask()
    r_b2020 = bank_2020_full.clip(geom).selfMask()
    r_dyn   = dyn_full.clip(geom).selfMask()
    
    map_b2010 = ee.data.getMapId({"image": r_b2010.visualize(palette=["#fbbf24"], min=0, max=1)})
    map_b2020 = ee.data.getMapId({"image": r_b2020.visualize(palette=["#ff2255"], min=0, max=1)})
    map_dyn   = ee.data.getMapId({"image": r_dyn.visualize(min=1, max=2, palette=["#ef4444", "#06b6d4"])})
    
    river_tile_data = {
        "id": r_id,
        "name": r_name,
        "province": r["province"],
        "island": r["island"],
        "bounds": bounds,
        "center": r["center"],
        "zoom": r.get("zoom", 11),
        "fromAsset": True,
        "asset2010": ASSET_2010,
        "asset2020": ASSET_2020,
        "assetDynamics": ASSET_DYN,
        "tile2010": map_b2010["tile_fetcher"].url_format,
        "tile2020": map_b2020["tile_fetcher"].url_format,
        "tileChange": map_dyn["tile_fetcher"].url_format,
        "colors": {
            "bank2010": "#fbbf24",
            "bank2020": "#ff2255",
            "erosi": "#ef4444",
            "akresi": "#06b6d4"
        }
    }
    
    # Simpan per-sungai ke cache
    cache_file = CACHE_DIR / f"{r_id}.json"
    with open(cache_file, "w") as f:
        json.dump(river_tile_data, f, indent=2)
        
    all_rivers_tiles[r_id] = river_tile_data

# Tulis ke gee_tiles_rivers.json di backend dan frontend
for out_p in [OUT_ALL_BE, OUT_ALL_FE]:
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(all_rivers_tiles, f, indent=2)
    print(f"✅ Berhasil menulis seluruh sungai ke {out_p}")

# File utama overview nasional
main_tiles_data = {
    "status": "ready",
    "source": "Google Earth Engine Asset Resmi (Indonesia Only)",
    "scope": "Indonesia Only - Dynamic Per River",
    "yearOld": 2010,
    "yearNew": 2020,
    "tileSat2010": map_sat_2010["tile_fetcher"].url_format,
    "tileSat2020": map_sat_2020["tile_fetcher"].url_format,
    "tile2010": None,
    "tile2020": None,
    "tileChange": None,
    "colors": {
        "bank2010": "#fbbf24",
        "bank2020": "#ff2255",
        "erosi": "#ef4444",
        "akresi": "#06b6d4"
    }
}

for out_m in [OUT_MAIN_BE, OUT_MAIN_FE]:
    out_m.parent.mkdir(parents=True, exist_ok=True)
    with open(out_m, "w") as f:
        json.dump(main_tiles_data, f, indent=2)
    print(f"✅ Berhasil menulis status basemap ke {out_m}")

print("🎉 Selesai! Garis batas pinggir sungai untuk SELURUH sungai di Indonesia kini sudah aktif dan tersimpan!")
