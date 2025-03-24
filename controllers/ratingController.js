const Rating = require('../models/rating');
const User = require('../models/user');
const Question = require('../models/question');

const { validationResult } = require('express-validator');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');

const saveRating = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { questionId, userId, rating } = req.body;

    const isQuestionExist = await Question.findByPk(questionId);

    if (!isQuestionExist) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Question not found' });
    }

    const isUserExist = await Question.findByPk(userId);

    if (isUserExist) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'User not found' });
    }

    const newSurvey = await Rating.create({ questionId, userId, rating });
    res.status(HTTP_STATUS_CODE.CREATED).json({
      message: 'Rating created successfully',
      survey: newSurvey,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error creating rating',
      error: error.message,
    });
  }
};

const updateRating = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { ratingId } = req.params;
    const { rating } = req.body;

    // Find the question by ID
    const record = await Rating.findByPk(ratingId);
    if (!record) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Rating not found' });
    }

    // Update the rating
    record.rating = rating;
    await record.save();

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Rating updated successfully',
      record,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error updating rating',
      error: error.message,
    });
  }
};

module.exports = { saveRating, updateRating };
