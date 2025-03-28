const { body } = require('express-validator');

const ratingValidation = [
  body('questionId').notEmpty().withMessage('questionId is required'),
  body('userId').notEmpty().withMessage('userId is required'),
  body('rating')
    .notEmpty()
    .withMessage('Rating is required')
    .isInt({ min: 1, max: 5 })
    .withMessage('Rating must be between 1 and 5'),
];

module.exports = {
  ratingValidation,
};
