const Rating = require('../models/rating');
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
    const { question_id, user_id, rating } = req.body;

    const isQuestionExist = await Question.findByPk(question_id);

    if (!isQuestionExist) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Question not found' });
    }

    // Check if user exists (this would be handled by your parent project)
    // For now, we'll assume the user exists since this is a microservice

    const newRating = await Rating.create({ 
      question_id, 
      user_id, 
      rating,
      status: 'ACTIVE'
    });
    res.status(HTTP_STATUS_CODE.CREATED).json({
      message: 'Rating created successfully',
      rating: newRating,
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
    const { rating, status } = req.body;

    // Find the rating by ID
    const record = await Rating.findByPk(ratingId);
    if (!record) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Rating not found' });
    }

    // Update the rating
    await record.update({ rating, status });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Rating updated successfully',
      rating: record,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error updating rating',
      error: error.message,
    });
  }
};

const getRatingById = async (req, res) => {
  try {
    const { ratingId } = req.params;

    const rating = await Rating.findByPk(ratingId);
    if (!rating) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Rating not found' });
    }

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Rating retrieved successfully',
      rating,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error retrieving rating',
      error: error.message,
    });
  }
};

const getRatingsByQuestion = async (req, res) => {
  try {
    const { question_id } = req.params;

    const ratings = await Rating.findAll({
      where: {
        question_id: question_id,
      },
    });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Ratings fetched successfully',
      ratings,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error fetching ratings',
      error: error.message,
    });
  }
};

const getRatingsByUser = async (req, res) => {
  try {
    const { userId } = req.params;

    const ratings = await Rating.findAll({
      where: { 
        user_id: userId,
        status: 'ACTIVE'
      }
    });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Ratings retrieved successfully',
      ratings,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error retrieving ratings',
      error: error.message,
    });
  }
};

const deleteRating = async (req, res) => {
  try {
    const { ratingId } = req.params;

    const rating = await Rating.findByPk(ratingId);
    if (!rating) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Rating not found' });
    }

    // Soft delete by updating status
    await rating.update({ status: 'DE_ACTIVE' });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Rating deleted successfully',
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error deleting rating',
      error: error.message,
    });
  }
};

const getAllRatings = async (req, res) => {
  try {
    const ratings = await Rating.findAll({
      where: { status: 'ACTIVE' }
    });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Ratings retrieved successfully',
      ratings,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error retrieving ratings',
      error: error.message,
    });
  }
};

module.exports = { 
  saveRating, 
  updateRating, 
  getRatingById, 
  getRatingsByQuestion, 
  getRatingsByUser,
  deleteRating,
  getAllRatings
};
