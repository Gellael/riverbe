const fs = require('fs');
const path = require('path');

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

    // Jika dipanggil dengan parameter river (misal: /api/tiles?river=kapuas)
    if (riverId) {
      const cleanId = String(riverId).toLowerCase().trim();

      // 1. Cek file cache per-sungai di cache/rivers/{cleanId}.json
      const riverCachePaths = [
        path.join(process.cwd(), 'cache', 'rivers', `${cleanId}.json`),
        path.join(__dirname, '..', 'cache', 'rivers', `${cleanId}.json`),
        path.join(process.cwd(), 'backend', 'cache', 'rivers', `${cleanId}.json`)
      ];

      for (const p of riverCachePaths) {
        if (fs.existsSync(p)) {
          const raw = fs.readFileSync(p, 'utf8');
          return res.status(200).json(JSON.parse(raw));
        }
      }

      // 2. Cek di gee_tiles_rivers.json (kumpulan seluruh sungai)
      const allRiversPaths = [
        path.join(process.cwd(), 'gee_tiles_rivers.json'),
        path.join(__dirname, '..', 'gee_tiles_rivers.json'),
        path.join(process.cwd(), 'backend', 'gee_tiles_rivers.json')
      ];

      for (const p of allRiversPaths) {
        if (fs.existsSync(p)) {
          const raw = fs.readFileSync(p, 'utf8');
          const all = JSON.parse(raw);
          if (all && all[cleanId]) {
            return res.status(200).json(all[cleanId]);
          }
        }
      }

      return res.status(404).json({
        error: `Sungai '${riverId}' belum tersedia di cache asset GEE.`,
        riverId: cleanId
      });
    }

    // Jika dipanggil tanpa parameter (Overview Nasional)
    const candidatePaths = [
      path.join(process.cwd(), 'gee_tiles.json'),
      path.join(__dirname, '..', 'gee_tiles.json'),
      path.join(process.cwd(), 'cache', 'gee_tiles.json')
    ];

    for (const p of candidatePaths) {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf8');
        const json = JSON.parse(raw);
        return res.status(200).json(json);
      }
    }

    return res.status(200).json({
      status: "ready",
      message: "Menunggu konfigurasi tile"
    });
  } catch (err) {
    return res.status(500).json({ error: String(err) });
  }
};
