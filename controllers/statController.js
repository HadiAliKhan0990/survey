const Rating = require('../models/rating');
const Question = require('../models/question');
const Survey = require('../models/survey');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');
const { Op } = require('sequelize');
const { validationResult } = require('express-validator');

const getTotalRatingByQuestionId = async (req, res) => {
  try {
    const { question_id } = req.params;

    const isQuestionExist = await Question.findByPk(question_id);

    if (!isQuestionExist) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Question not found' });
    }

    // Fetch all ratings for the given question_id
    const ratings = await Rating.findAll({
      where: { question_id: question_id },
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
    const { survey_id } = req.params;

    // Check if the survey exists
    const survey = await Survey.findByPk(survey_id, {
      include: Question, // Include associated questions
    });

    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'Survey not found' });
    }

    const question_ids = Array.from(survey.Questions, ({ id }) => id);

    if (!Array.isArray(question_ids) || question_ids.length === 0) {
      return res
        .status(HTTP_STATUS_CODE.BAD_REQUEST)
        .json({ message: 'question_ids must be a non-empty array' });
    }

    // Fetch all ratings where question_id is in the question_ids array
    const ratings = await Rating.findAll({
      where: { question_id: { [Op.in]: question_ids } },
    });

    // Group ratings by question_id and calculate total rating for each question
    const ratingsMap = {};

    ratings.forEach(({ question_id, rating }) => {
      if (!ratingsMap[question_id]) {
        ratingsMap[question_id] = 0;
      }
      ratingsMap[question_id] += rating;
    });

    // Prepare the response data
    const results = question_ids.map((question_id) => ({
      question_id,
      totalRating: ratingsMap[question_id] || 0, // Default to 0 if no ratings found
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

    const question_ids = Array.from(survey.Questions, ({ id }) => id);

    const ratings = await Rating.findAll({
      where: {
        updatedAt: {
          [Op.between]: [new Date(startDate), new Date(endDate)],
        },
        question_id: {
          [Op.in]: question_ids,
        },
      },
    });

    // Group ratings by question_id and calculate total rating for each question
    const ratingsMap = {};

    ratings.forEach(({ question_id, rating }) => {
      if (!ratingsMap[question_id]) {
        ratingsMap[question_id] = 0;
      }
      ratingsMap[question_id] += rating;
    });

    // Prepare the response data
    const results = question_ids.map((question_id) => ({
      question_id,
      totalRating: ratingsMap[question_id] || 0, // Default to 0 if no ratings found
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
