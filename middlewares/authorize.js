const jwt = require('jsonwebtoken');
const User = require('../models/user');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');

exports.authorizeMiddleware = (requiredRoles) => {
  return async (req, res, next) => {
    try {
      const authHeader = req.headers.authorization;

      const token = authHeader.split(' ')[1];

      const decoded = jwt.verify(token, process.env.JWT_SECRET_KEY);

      const user = await User.findByPk(decoded.userId);

      if (!user) {
        return res
          .status(HTTP_STATUS_CODE.UNAUTHORIZED)
          .json({ message: 'Unauthorized: User not found.' });
      }

      if (!requiredRoles.includes(user.role)) {
        return res
          .status(HTTP_STATUS_CODE.FORBIDDEN)
          .json({ message: 'Forbidden: Insufficient permissions.' });
      }

      // req.user = user; // Attach user to request for further use

      next();
    } catch (error) {
      return res.status(401).json({
        message: 'Unauthorized: Invalid token.',
        error: error.message,
      });
    }
  };
};
