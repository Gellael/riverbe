module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    service: "INARivers Backend API",
    status: "online",
    endpoints: {
      health: "/api/health",
      tiles: "/api/tiles"
    }
  });
};

