const Survey = require('../models/survey');
const { validationResult } = require('express-validator');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');

const saveSurvey = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { name, heading } = req.body;

    const newSurvey = await Survey.create({ name, heading });
    res.status(HTTP_STATUS_CODE.CREATED).json({
      message: 'Survey created successfully',
      survey: newSurvey,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error creating survey',
      error: error.message,
    });
  }
};
const getAllSurveys = async (req, res) => {
  try {
    const surveys = await Survey.findAll();
    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Surveys retrieved successfully',
      surveys,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error retrieving surveys',
      error: error.message,
    });
  }
};

module.exports = { saveSurvey, getAllSurveys };
