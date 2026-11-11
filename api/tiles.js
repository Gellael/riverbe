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
      message: "Menunggu file gee_tiles.json"
    });
  } catch (err) {
    return res.status(500).json({ error: String(err) });
  }
};
