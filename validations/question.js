const { body } = require('express-validator');
const { param } = require('express-validator');

const questionValidations = [
  body('text')
    .notEmpty()
    .withMessage('Question text is required')
    .isString()
    .withMessage('Question text must be a string')
    .trim()
    .isLength({ min: 1, max: 1000 })
    .withMessage('Question text must be between 1 and 1000 characters'),
  
  body('status')
    .optional()
    .isIn(['ACTIVE', 'PENDING', 'DE_ACTIVE'])
    .withMessage('Status must be one of: ACTIVE, PENDING, DE_ACTIVE'),
];

const surveyIdValidations = [
  param('survey_id')
    .notEmpty()
    .withMessage('Survey ID is required')
    .isUUID()
    .withMessage('Survey ID must be a valid UUID'),
];

const questionIdValidations = [
  param('question_id')
    .notEmpty()
    .withMessage('Question ID is required')
    .isUUID()
    .withMessage('Question ID must be a valid UUID'),
];

module.exports = {
  questionValidations,
  surveyIdValidations,
  questionIdValidations,
};
