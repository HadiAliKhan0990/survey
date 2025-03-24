const jwt = require('jsonwebtoken');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');

exports.authMiddleware = (req, res, next) => {
  const token =
    req.headers.authorization && req.headers.authorization.split(' ')[1];

  if (!token) {
    return res
      .status(HTTP_STATUS_CODE.UNAUTHORIZED)
      .json({ message: 'No token provided' });
  }

  jwt.verify(token, process.env.JWT_SECRET_KEY, (err, decoded) => {
    if (err) {
      // Here, err.message will indicate if the token is expired
      if (err.name === 'TokenExpiredError') {
        return res
          .status(HTTP_STATUS_CODE.UNAUTHORIZED)
          .json({ message: 'Token has expired' });
      } else if (err.name === 'JsonWebTokenError') {
        return res
          .status(HTTP_STATUS_CODE.UNAUTHORIZED)
          .json({ message: 'Invalid token' });
      } else if (err.name === 'NotBeforeError') {
        return res
          .status(HTTP_STATUS_CODE.UNAUTHORIZED)
          .json({ message: 'Token not active yet' });
      }
      return res
        .status(HTTP_STATUS_CODE.UNAUTHORIZED)
        .json({ message: 'Failed to authenticate token' });
    }

    // Save user ID from the token to request for use in other routes
    // req.userId = decoded.userId;

    next();
  });
};
