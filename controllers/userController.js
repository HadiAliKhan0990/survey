const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const User = require('../models/user');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');
const { validationResult } = require('express-validator');
const roles = require('../utils/role');

const generateAccessToken = (userId) => {
  return jwt.sign({ userId }, process.env.JWT_SECRET_KEY, {
    expiresIn: process.env.ACCESS_TOKEN_EXPIRY,
  });
};

const generateRefreshToken = (userId) => {
  return jwt.sign({ userId }, process.env.JWT_REFRESH_SECRET_KEY, {
    expiresIn: process.env.REFRESH_TOKEN_EXPIRY,
  });
};

const register = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  const { username, email, password, role = roles.User } = req.body;

  try {
    // Check if user already exists
    const existingUser = await User.findOne({ where: { email } });
    if (existingUser) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'User already exists' });
    }

    // Hash the password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create new user
    const newUser = await User.create({
      username,
      email,
      password: hashedPassword,
      role: role,
    });

    // Generate JWT token
    const token = jwt.sign({ userId: newUser.id }, process.env.JWT_SECRET_KEY, {
      expiresIn: process.env.ACCESS_TOKEN_EXPIRY,
    });

    delete newUser.dataValues.password;
    const data = { ...newUser.dataValues, token };

    res
      .status(HTTP_STATUS_CODE.CREATED)
      .json({ message: 'User registered successfully', data });
  } catch (error) {
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Error registering user', error });
  }
};

const login = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  const { email, password } = req.body;

  try {
    // Find user by email (Include password)
    const user = await User.findOne({
      where: { email }, // ✅ Include password
    });

    if (!user) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'User not found' });
    }

    // Check if password exists (prevents undefined error)
    if (!user.password) {
      return res
        .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
        .json({ message: 'User password not found' });
    }

    // Compare password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      return res
        .status(HTTP_STATUS_CODE.UNAUTHORIZED)
        .json({ message: 'Invalid password' });
    }

    // Generate JWT token
    const token = jwt.sign({ userId: user.id }, process.env.JWT_SECRET_KEY, {
      expiresIn: process.env.ACCESS_TOKEN_EXPIRY,
    });

    // Remove password from response
    const { password: _, ...userData } = user.dataValues;
    res
      .status(HTTP_STATUS_CODE.OK)
      .json({ message: 'Login successful', data: { ...userData, token } });
  } catch (error) {
    console.error('Login error:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Error logging in', error });
  }
};

const resetPassword = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  const { email, newPassword } = req.body;

  try {
    // Find user by email
    const user = await User.findOne({ where: { email } });
    if (!user) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'User not found' });
    }

    // Hash the new password
    const hashedPassword = await bcrypt.hash(newPassword, 10);

    // Update the user's password
    user.password = hashedPassword;
    await user.save();

    res
      .status(HTTP_STATUS_CODE.OK)
      .json({ message: 'Password reset successful' });
  } catch (error) {
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Error resetting password', error });
  }
};

module.exports = {
  generateAccessToken,
  generateRefreshToken,
  register,
  login,
  resetPassword,
};
