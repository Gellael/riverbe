const fs = require('fs');
const path = require('path');

// Menggunakan require() statis agar Vercel NFT (Node File Trace) 100% mem-bundle file JSON ini ke serverless container
let defaultTiles = null;
try {
  defaultTiles = require('../gee_tiles.json');
} catch (e) {
  try {
    defaultTiles = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'gee_tiles.json'), 'utf8'));
  } catch (err) {}
}

let allRiversData = null;
try {
  allRiversData = require('../gee_tiles_rivers.json');
} catch (e) {
  try {
    allRiversData = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'gee_tiles_rivers.json'), 'utf8'));
  } catch (err) {}
}

module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');
  res.setHeader('Cache-Control', 'public, max-age=43200, s-maxage=86400');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    const riverId = url.searchParams.get('river') || req.query?.river;

    // 1. Jika meminta tile sungai tertentu (?river=kapuas, ?river=bengkulu, dll)
    if (riverId) {
      const cleanId = String(riverId).toLowerCase().trim();

      // Cek dari allRiversData yang di-bundle
      if (allRiversData && allRiversData[cleanId]) {
        return res.status(200).json(allRiversData[cleanId]);
      }

      // Cek dari cache/rivers/{cleanId}.json jika ada
      const cachePath = path.join(__dirname, '..', 'cache', 'rivers', `${cleanId}.json`);
      if (fs.existsSync(cachePath)) {
        const raw = fs.readFileSync(cachePath, 'utf8');
        return res.status(200).json(JSON.parse(raw));
      }

      return res.status(404).json({
        error: `Sungai '${riverId}' belum tersedia di asset GEE.`,
        riverId: cleanId
      });
    }

    // 2. Jika meminta konfigurasi umum / overview nasional
    if (defaultTiles) {
      return res.status(200).json(defaultTiles);
    }

    // Fallback baca file lokal jika defaultTiles null
    const candidatePaths = [
      path.join(__dirname, '..', 'gee_tiles.json'),
      path.join(process.cwd(), 'gee_tiles.json')
    ];

    for (const p of candidatePaths) {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf8');
        return res.status(200).json(JSON.parse(raw));
      }
    }

    return res.status(200).json({
      status: "ready",
      message: "Konfigurasi tile GEE aktif",
      riversCount: allRiversData ? Object.keys(allRiversData).length : 0
    });
  } catch (err) {
    return res.status(500).json({ error: String(err) });
  }
};
