import json
import ee
from pathlib import Path

key = json.loads(Path("gee-key.json").read_text())
PROJECT_ID = key["project_id"]
ee.Initialize(ee.ServiceAccountCredentials(key["client_email"], key_data=json.dumps(key)), project=PROJECT_ID)

print(f"Project ID: {PROJECT_ID}")
assets = ee.data.listAssets({"parent": f"projects/{PROJECT_ID}/assets"})
for a in assets.get("assets", []):
    print(f"- {a['id']} ({a['type']})")

