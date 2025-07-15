const { body } = require('express-validator');

const ratingValidation = [
  body('question_id').notEmpty().withMessage('question Id is required'),
  body('user_id').notEmpty().withMessage('user Id is required'),
  body('rating')
    .notEmpty()
    .withMessage('Rating is required')
    .isInt({ min: 1, max: 5 })
    .withMessage('Rating must be between 1 and 5'),
];

module.exports = {
  ratingValidation,
};
