const jwt = require('jsonwebtoken');

const verifyToken = async (req, res, next) => {
  let token = req.headers["authorization"];

  if (!token) {
    return res.status(403).send({
      status: false,
      status_msg: "A token is required for authentication",
      data: undefined
    });
  }

  token = token.split(" ")[1];
  
  try {
    const decoded = jwt.verify(token, process.env.AUTH_KEY);
    
    // Add decoded user info to request object
    req.user = decoded;
    return next();
  } catch (err) {
    return res.status(401).send({
      status: false,
      status_msg: "Invalid Token",
      data: undefined
    });
  }
};

// Optional middleware for admin-only routes
const requireAdmin = async (req, res, next) => {
  try {
    // Check if user is admin (you can customize this based on your user categories)
    if (req.user.user_category !== 2) { // Assuming category_id 2 is admin
      return res.status(403).send({
        status: false,
        status_msg: "Access denied. Admin privileges required.",
        data: undefined
      });
    }
    return next();
  } catch (error) {
    return res.status(500).send({
      status: false,
      status_msg: "Error checking admin privileges.",
      data: undefined
    });
  }
};

module.exports = { verifyToken, requireAdmin }; 