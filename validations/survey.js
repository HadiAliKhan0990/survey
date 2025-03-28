const { body } = require('express-validator');

const surveyValidations = [
  body('name').notEmpty().withMessage('Survey name is required'),
  body('heading').notEmpty().withMessage('Survey heading is required'),
];

module.exports = {
  surveyValidations,
};
