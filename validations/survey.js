const { body } = require('express-validator');

const surveyValidations = [
  body('name')
    .trim()
    .notEmpty()
    .withMessage('Survey name is required'),
  body('heading')
    .trim()
    .notEmpty()
    .withMessage('Survey heading is required'),
  body('company_name')
    .trim()
    .notEmpty()
    .withMessage('Company name is required'),
];

module.exports = {
  surveyValidations,
};
