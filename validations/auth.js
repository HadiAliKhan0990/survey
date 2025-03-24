const { body } = require('express-validator');

const registerValidation = [
  body('username').notEmpty().withMessage('Username is required'),
  body('email').isEmail().withMessage('Please provide a valid email address'),
  body('password')
    .isLength({ min: 8 })
    .withMessage('Password must be at least 8 characters long')
    .matches(/\d/)
    .withMessage('Password must contain a number')
    .matches(/[!@#$%^&*]/)
    .withMessage('Password must contain a special character'),
];

const loginValidation = [
  body('email').isEmail().withMessage('Please provide a valid email address'),
  body('password').notEmpty().withMessage('Password is required'),
];

const resetPasswordValidation = [
  body('email').isEmail().withMessage('Please provide a valid email address'),
  body('newPassword')
    .isLength({ min: 8 })
    .withMessage('New password must be at least 8 characters long')
    .matches(/\d/)
    .withMessage('New password must contain a number')
    .matches(/[!@#$%^&*]/)
    .withMessage('New password must contain a special character'),
];

module.exports = {
  registerValidation,
  loginValidation,
  resetPasswordValidation,
};
