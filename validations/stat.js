const { query } = require('express-validator');
const { param } = require('express-validator');

const graphStatValidations = [
  query('startDate')
    .notEmpty()
    .withMessage('startDate is required')
    .isISO8601()
    .withMessage('startDate must be a valid date'),

  query('endDate')
    .notEmpty()
    .withMessage('endDate is required')
    .isISO8601()
    .withMessage('endDate must be a valid date'),

  query('survey_id').notEmpty().withMessage('survey Id is required'),
];

const questionsWithStatsValidations = [
  param('survey_id').notEmpty().withMessage('survey Id is required'),
];

module.exports = { graphStatValidations, questionsWithStatsValidations };
