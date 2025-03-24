const express = require('express');

const { authorizeMiddleware } = require('../middlewares/authorize');

const roles = require('../utils/role');

const {
  graphStatValidations,
  questionsWithStatsValidations,
} = require('../validations/stat');

const {
  getTotalRatingByQuestionId,
  getTotalRatingsForQuestions,
  getRatingsByDateRange,
} = require('../controllers/statController');

const router = express.Router();

// router.get(
//   '/:questionId',
//   authorizeMiddleware([roles.Admin]),
//   getTotalRatingByQuestionId
// );

router.get(
  '/:surveyId',
  authorizeMiddleware([roles.Admin]),
  questionsWithStatsValidations,
  getTotalRatingsForQuestions
);

router.get(
  '/',
  authorizeMiddleware([roles.Admin]),
  graphStatValidations,
  getRatingsByDateRange
);

module.exports = router;
