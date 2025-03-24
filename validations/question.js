const { body } = require('express-validator');
const { param } = require('express-validator');

const questionValidations = [
  body('text').notEmpty().withMessage('question is required'),
];

const surveyIdValidations = [
  param('surveyId').notEmpty().withMessage('question is required'),
];

const questionIdValidations = [
  param('questionId').notEmpty().withMessage('question is required'),
];

module.exports = {
  questionValidations,
  surveyIdValidations,
  questionIdValidations,
};
