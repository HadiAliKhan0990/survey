const express = require('express');
const { verifyToken, requireAdmin } = require('../middlewares/authMiddleware');

const {
  getTotalRatingByQuestionId,
  getTotalRatingsForQuestions,
  getRatingsByDateRange,
} = require('../controllers/statController');

const {
  graphStatValidations,
  questionsWithStatsValidations,
} = require('../validations/stat');

const router = express.Router();

// Admin only routes
router.get(
  '/:survey_id',
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

router.get(
  '/question/:question_id',
  verifyToken,
  requireAdmin,
  getTotalRatingByQuestionId
);

module.exports = router;
