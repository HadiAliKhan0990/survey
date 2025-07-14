const express = require('express');
const { verifyToken, requireAdmin } = require('../middlewares/authMiddleware');

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

// Admin only routes
router.get(
  '/:surveyId',
  verifyToken,
  requireAdmin,
  questionsWithStatsValidations,
  getTotalRatingsForQuestions
);

router.get(
  '/',
  verifyToken,
  requireAdmin,
  graphStatValidations,
  getRatingsByDateRange
);

// Uncomment if you want to add this route
// router.get(
//   '/question/:questionId',
//   verifyToken,
//   requireAdmin,
//   getTotalRatingByQuestionId
// );

module.exports = router;
