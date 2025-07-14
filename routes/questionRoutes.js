const express = require('express');
const { verifyToken, requireAdmin } = require('../middlewares/authMiddleware');

const {
  createQuestionForSurvey,
  getQuestionsForSurvey,
  updateQuestion,
  deleteQuestion,
  getQuestionById,
  getAllQuestions
} = require('../controllers/questionController');

const {
  questionValidations,
  surveyIdValidations,
  questionIdValidations,
} = require('../validations/question');

const router = express.Router();

// Public routes (no authentication required)
router.get('/public', getAllQuestions);
router.get('/public/:surveyId', surveyIdValidations, getQuestionsForSurvey);

// Admin only routes
router.get('/', verifyToken, requireAdmin, getAllQuestions);
router.get('/:surveyId', verifyToken, requireAdmin, surveyIdValidations, getQuestionsForSurvey);
router.get('/question/:questionId', verifyToken, requireAdmin, questionIdValidations, getQuestionById);

router.post(
  '/:surveyId',
  verifyToken,
  requireAdmin,
  questionValidations,
  createQuestionForSurvey
);

router.put(
  '/:questionId',
  verifyToken,
  requireAdmin,
  questionIdValidations,
  questionValidations,
  updateQuestion
);

router.delete('/:questionId', verifyToken, requireAdmin, questionIdValidations, deleteQuestion);

module.exports = router;
