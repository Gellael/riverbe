/**
 * =====================================================================
 * Google Earth Engine (GEE) - Bibir Sungai & Dinamika Pergeseran Indonesia
 * Skrip Resmi Komparasi: Tahun 2010 vs Tahun 2020 + Citra Satelit Landsat
 * Lingkup: Seluruh Sungai di Indonesia
 * =====================================================================
 * Cara Penggunaan di Code Editor (code.earthengine.google.com):
 * 1. Buka https://code.earthengine.google.com/
 * 2. Buat skrip baru, paste kode ini, lalu klik 'Run'.
 * 3. Buka tab 'Tasks' di sebelah kanan untuk mengekspor Asset permanen.
 */

var YEAR_OLD = 2010;
var YEAR_NEW = 2020;
var PROJECT_ID = 'project-gis-494114';

// 1. Batas Daratan Nasional Indonesia (USDOS LSIB)
var indo_fc = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
  .filter(ee.Filter.eq('country_na', 'Indonesia'));
var indo_mask = ee.Image.constant(1).clip(indo_fc).mask();
var indo_geom = ee.Geometry.Rectangle([94.5, -11.5, 141.5, 6.5], null, false);

// 2. Citra Satelit Landsat 2010 (True Color Bebas Awan)
var l7_2010 = ee.ImageCollection('LANDSAT/LE07/C02/T1').filterDate('2009-06-01', '2011-06-30');
var l5_2010 = ee.ImageCollection('LANDSAT/LT05/C02/T1').filterDate('2009-06-01', '2011-06-30');
var comp_2010 = ee.Algorithms.Landsat.simpleComposite(l7_2010.merge(l5_2010), true);
var sat_2010_rgb = comp_2010.select(['B3', 'B2', 'B1']).updateMask(indo_mask);

// 3. Jaringan Sungai MERIT Hydro (upa >= 30 km^2) + Land Drainage Mask
var hydro = ee.Image('MERIT/Hydro/v1_0_1');
var land_drainage = hydro.select('dir').mask().and(hydro.select('elv').gte(1));
var river_net = hydro.select('upa').gte(30).selfMask();

// Koridor sungai 400m di sepanjang sungai daratan Indonesia (tanpa pantai laut)
var corridor = river_net.focalMax(400, 'circle', 'meters')
  .updateMask(indo_mask)
  .updateMask(land_drainage)
  .selfMask();

// 4. Air Permanen (waterClass == 3)
var jrc_2010 = ee.ImageCollection('JRC/GSW1_4/YearlyHistory')
  .filter(ee.Filter.eq('year', YEAR_OLD)).first().select('waterClass');
var jrc_2020 = ee.ImageCollection('JRC/GSW1_4/YearlyHistory')
  .filter(ee.Filter.eq('year', YEAR_NEW)).first().select('waterClass');

var w2010 = jrc_2010.eq(3).updateMask(corridor).selfMask();
var w2020 = jrc_2020.eq(3).updateMask(corridor).selfMask();

// 5. Ekstraksi Garis Bibir Tebing Sungai (Banklines)
var b2010 = w2010.unmask(0).focalMax(1, 'square', 'pixels')
  .subtract(w2010.unmask(0).focalMin(1, 'square', 'pixels'))
  .gt(0).selfMask();

var b2020 = w2020.unmask(0).focalMax(1, 'square', 'pixels')
  .subtract(w2020.unmask(0).focalMin(1, 'square', 'pixels'))
  .gt(0).selfMask();

// 6. Dinamika: Erosi (Merah) & Akresi (Cyan)
var erosi = w2020.unmask(0).and(w2010.unmask(0).not()).selfMask();
var akresi = w2010.unmask(0).and(w2020.unmask(0).not()).selfMask();

var change_img = ee.Image(0).byte()
  .where(erosi, 1)
  .where(akresi, 2)
  .selfMask();

// ================= VISUALISASI DI PETA =================
Map.centerObject(indo_fc, 5);

// Layer Citra Satelit Landsat 2010
Map.addLayer(
  sat_2010_rgb,
  {bands: ['B3', 'B2', 'B1'], min: 0.03, max: 0.25, gamma: 1.3},
  '🛰️ Citra Satelit Landsat 2010 (True Color)'
);

// Layer Dinamika
Map.addLayer(
  change_img,
  {min: 1, max: 2, palette: ['#ef4444', '#06b6d4'], opacity: 0.85},
  'Zona Dinamika (1=Erosi Merah, 2=Akresi Cyan)'
);

// Layer Garis Bibir 2010 (Kuning Emas)
Map.addLayer(
  b2010,
  {palette: ['#fbbf24']},
  'Garis Bibir Sungai 2010 (Kuning Emas)'
);

// Layer Garis Bibir 2020 (Pink Terang)
Map.addLayer(
  b2020,
  {palette: ['#ff2255']},
  'Garis Bibir Sungai 2020 (Pink/Merah Terang)'
);

// ================= EKSPOR KE ASSET GEE =================
var assetPath = 'projects/' + PROJECT_ID + '/assets/';

Export.image.toAsset({
  image: comp_2010.select(['B3', 'B2', 'B1']).multiply(255).byte().clip(indo_fc),
  description: 'Ekspor_Citra_Landsat_2010',
  assetId: assetPath + 'citra_landsat_2010',
  region: indo_geom,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toAsset({
  image: b2010.byte().rename('bank_2010'),
  description: 'Ekspor_Bibir_2010',
  assetId: assetPath + 'bibir_sungai_2010',
  region: indo_geom,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toAsset({
  image: b2020.byte().rename('bank_2020'),
  description: 'Ekspor_Bibir_2020',
  assetId: assetPath + 'bibir_sungai_2020',
  region: indo_geom,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toAsset({
  image: change_img.rename('dinamika_2010_2020'),
  description: 'Ekspor_Dinamika_2010_2020',
  assetId: assetPath + 'dinamika_pergeseran_2010_2020',
  region: indo_geom,
  scale: 30,
  maxPixels: 1e13
});

print('✅ Skrip berhasil dimuat! Buka tab Tasks untuk menjalankan ekspor.');
