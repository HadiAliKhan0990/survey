const express = require('express');
const router = express.Router();
const { register, login, resetPassword } = require('../controllers/userController');

const { registerValidation, loginValidation, resetPasswordValidation } = require('../validations/auth');

router.post('/register', registerValidation, register);

router.post('/login', loginValidation, login);

router.post('/reset-password', resetPasswordValidation, resetPassword);

module.exports = router;
