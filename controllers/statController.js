const Rating = require('../models/rating');
const Question = require('../models/question');
const Survey = require('../models/survey');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');
const { Op } = require('sequelize');
const { validationResult } = require('express-validator');

const getTotalRatingByQuestionId = async (req, res) => {
  try {
    const { questionId } = req.params;

    const isQuestionExist = await Question.findByPk(questionId);

    if (!isQuestionExist) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Question not found' });
    }

    // Fetch all ratings for the given questionId
    const ratings = await Rating.findAll({
      where: { questionId: questionId },
    });

    // Calculate totalRating (sum of all ratings)
    const totalRating = ratings.reduce((sum, record) => sum + record.rating, 0);

    return res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Ratings fetched successfully',
      totalRating,
      data: ratings,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error fetching total ratings',
      error: error.message,
    });
  }
};
const getTotalRatingsForQuestions = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { surveyId } = req.params;

    // Check if the survey exists
    const survey = await Survey.findByPk(surveyId, {
      include: Question, // Include associated questions
    });

    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Survey not found' });
    }

    const questionIds = Array.from(survey.Questions, ({ id }) => id);

    if (!Array.isArray(questionIds) || questionIds.length === 0) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'questionIds must be a non-empty array' });
    }

    // Fetch all ratings where questionId is in the questionIds array
    const ratings = await Rating.findAll({
      where: { questionId: { [Op.in]: questionIds } },
    });

    // Group ratings by questionId and calculate total rating for each question
    const ratingsMap = {};

    ratings.forEach(({ questionId, rating }) => {
      if (!ratingsMap[questionId]) {
        ratingsMap[questionId] = 0;
      }
      ratingsMap[questionId] += rating;
    });

    // Prepare the response data
    const results = questionIds.map((questionId) => ({
      questionId,
      totalRating: ratingsMap[questionId] || 0, // Default to 0 if no ratings found
    }));

    return res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Ratings fetched successfully',
      data: results,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error fetching ratings',
      error: error.message,
    });
  }
};

const getRatingsByDateRange = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { startDate, endDate, surveyId } = req.query;

    // Check if the survey exists
    const survey = await Survey.findByPk(surveyId, {
      include: Question, // Include associated questions
    });

    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Survey not found' });
    }

    const questionIds = Array.from(survey.Questions, ({ id }) => id);

    const ratings = await Rating.findAll({
      where: {
        updatedAt: {
          [Op.between]: [new Date(startDate), new Date(endDate)],
        },
        questionId: {
          [Op.in]: questionIds,
        },
      },
    });

    // Group ratings by questionId and calculate total rating for each question
    const ratingsMap = {};

    ratings.forEach(({ questionId, rating }) => {
      if (!ratingsMap[questionId]) {
        ratingsMap[questionId] = 0;
      }
      ratingsMap[questionId] += rating;
    });

    // Prepare the response data
    const results = questionIds.map((questionId) => ({
      questionId,
      totalRating: ratingsMap[questionId] || 0, // Default to 0 if no ratings found
    }));

    return res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Success',
      data: results,
    });
  } catch (error) {
    console.error('Error fetching ratings:', error);
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

module.exports = {
  getTotalRatingByQuestionId,
  getTotalRatingsForQuestions,
  getRatingsByDateRange,
};
