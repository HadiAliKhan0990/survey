const express = require('express');

const { authorizeMiddleware } = require('../middlewares/authorize');

const roles = require('../utils/role');

const { saveRating, updateRating } = require('../controllers/ratingController');

const { ratingValidation } = require('../validations/rating');

const router = express.Router();

router.post(
  '/',
  authorizeMiddleware([roles.User]),
  ratingValidation,
  saveRating
);

router.put('/:ratingId', authorizeMiddleware([roles.User]), updateRating);

module.exports = router;
