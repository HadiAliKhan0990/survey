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
    const survey = await Survey.findByPk(surveyId, {
      include: Question, // Include associated questions
    });

    if (!survey) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Survey not found' });
    }

    res.status(HTTP_STATUS_CODE.OK).json({ questions: survey.Questions }); // Send questions in response
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
    const question = await Question.create({ text });

    // Associate the question with the survey
    await survey.addQuestion(question);

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
    const { text } = req.body;

    // Find the question by ID
    const question = await Question.findByPk(questionId);
    if (!question) {
      return res
        .status(HTTP_STATUS_CODE.NOT_FOUND)
        .json({ message: 'Question not found' });
    }

    // Update the question text
    question.text = text;
    await question.save();

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

module.exports = { updateQuestion };

module.exports = {
  createQuestionForSurvey,
  getQuestionsForSurvey,
  updateQuestion,
};
