const express = require('express');

const { authorizeMiddleware } = require('../middlewares/authorize');

const roles = require('../utils/role');

const {
  createQuestionForSurvey,
  getQuestionsForSurvey,
  updateQuestion,
} = require('../controllers/questionController');

const {
  questionValidations,
  surveyIdValidations,
  questionIdValidations,
} = require('../validations/question');

const router = express.Router();

router.get('/:surveyId', surveyIdValidations, getQuestionsForSurvey);

router.post(
  '/:surveyId',
  authorizeMiddleware([roles.Admin]),
  questionValidations,
  createQuestionForSurvey
);

router.put(
  '/:questionId',
  authorizeMiddleware([roles.Admin]),
  questionIdValidations,
  updateQuestion
);

module.exports = router;
