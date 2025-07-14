const Question = require('../models/question');
const Survey = require('../models/survey');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');
const { validationResult } = require('express-validator');

const getQuestionsForSurvey = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { surveyId } = req.params;

    // Check if the survey exists
    const survey = await Survey.findByPk(surveyId);
    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Survey not found' });
    }

    // Get questions for this survey
    const questions = await Question.findAll({
      where: { 
        survey_id: surveyId,
        status: 'ACTIVE'
      }
    });

    res.status(HTTP_STATUS_CODE.OK).json({ questions });
  } catch (error) {
    console.error('Error fetching questions:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

const createQuestionForSurvey = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { surveyId } = req.params;
    const { text } = req.body;

    // Check if the survey exists
    const survey = await Survey.findByPk(surveyId);
    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Survey not found' });
    }

    // Create the question
    const question = await Question.create({ 
      text,
      survey_id: surveyId,
      status: 'ACTIVE'
    });

    res
      .status(HTTP_STATUS_CODE.CREATED)
      .json({ message: 'Question added successfully', question });
  } catch (error) {
    console.error('Error creating question:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

// Update a question by ID
const updateQuestion = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { questionId } = req.params;
    const { text, status } = req.body;

    // Find the question by ID
    const question = await Question.findByPk(questionId);
    if (!question) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Question not found' });
    }

    // Update the question
    await question.update({ text, status });

    res
      .status(HTTP_STATUS_CODE.OK)
      .json({ message: 'Question updated successfully', question });
  } catch (error) {
    console.error('Error updating question:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

const deleteQuestion = async (req, res) => {
  try {
    const { questionId } = req.params;

    // Find the question by ID
    const question = await Question.findByPk(questionId);
    if (!question) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Question not found' });
    }

    // Soft delete by updating status
    await question.update({ status: 'DE_ACTIVE' });

    res
      .status(HTTP_STATUS_CODE.OK)
      .json({ message: 'Question deleted successfully' });
  } catch (error) {
    console.error('Error deleting question:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

const getQuestionById = async (req, res) => {
  try {
    const { questionId } = req.params;

    // Find the question by ID
    const question = await Question.findByPk(questionId);
    if (!question) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Question not found' });
    }

    res
      .status(HTTP_STATUS_CODE.OK)
      .json({ question });
  } catch (error) {
    console.error('Error fetching question:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

const getAllQuestions = async (req, res) => {
  try {
    const questions = await Question.findAll({
      where: { status: 'ACTIVE' }
    });

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Questions retrieved successfully',
      questions,
    });
  } catch (error) {
    console.error('Error fetching questions:', error);
    res
      .status(HTTP_STATUS_CODE.INTERNAL_SERVER)
      .json({ message: 'Internal server error' });
  }
};

module.exports = {
  createQuestionForSurvey,
  getQuestionsForSurvey,
  updateQuestion,
  deleteQuestion,
  getQuestionById,
  getAllQuestions,
};
