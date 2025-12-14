const Survey = require('../models/survey');
const { validationResult } = require('express-validator');
const { HTTP_STATUS_CODE } = require('../utils/httpStatus');
const { Op } = require('sequelize');

const saveSurvey = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { name, heading, company_name, user_id } = req.body;

    const newSurvey = await Survey.create({ 
      name, 
      heading, 
      company_name,
      user_id,
      status: 'ACTIVE'
    });
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
    const { company_name } = req.query;
    const whereClause = { status: 'ACTIVE' };

    if (company_name) {
      whereClause.company_name = {
        [Op.like]: `%${company_name.trim()}%`,
      };
    }

    const surveys = await Survey.findAll({
      where: whereClause
    });
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

const getSurveyById = async (req, res) => {
  try {
    const { id } = req.params;
    const survey = await Survey.findByPk(id);
    
    if (!survey) {
      return res.status(HTTP_STATUS_CODE.NOT_FOUND).json({
        message: 'Survey not found',
      });
    }

    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Survey retrieved successfully',
      survey,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error retrieving survey',
      error: error.message,
    });
  }
};

const updateSurvey = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res
      .status(HTTP_STATUS_CODE.BAD_REQUEST)
      .json({ errors: errors.array() });
  }

  try {
    const { id } = req.params;
    const { name, heading, company_name, status } = req.body;

    const survey = await Survey.findByPk(id);
    if (!survey) {
      return res.status(HTTP_STATUS_CODE.NOT_FOUND).json({
        message: 'Survey not found',
      });
    }

    await survey.update({ name, heading, company_name, status });
    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Survey updated successfully',
      survey,
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error updating survey',
      error: error.message,
    });
  }
};

const deleteSurvey = async (req, res) => {
  try {
    const { id } = req.params;
    const survey = await Survey.findByPk(id);
    
    if (!survey) {
      return res.status(HTTP_STATUS_CODE.NOT_FOUND).json({
        message: 'Survey not found',
      });
    }

    await survey.update({ status: 'DE_ACTIVE' });
    res.status(HTTP_STATUS_CODE.OK).json({
      message: 'Survey deleted successfully',
    });
  } catch (error) {
    res.status(HTTP_STATUS_CODE.INTERNAL_SERVER).json({
      message: 'Error deleting survey',
      error: error.message,
    });
  }
};

const getSurveysByUserId = async (req, res) => {
  try {
    const { userId } = req.params;
    const { company_name } = req.query;
    const whereClause = {
      user_id: userId,
      status: 'ACTIVE',
    };

    if (company_name) {
      whereClause.company_name = {
        [Op.like]: `%${company_name.trim()}%`,
      };
    }

    const surveys = await Survey.findAll({
      where: whereClause,
    });
    
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

const getSurveysByCompanyName = async (req, res) => {
  try {
    const { companyName } = req.params;

    const surveys = await Survey.findAll({
      where: {
        company_name: {
          [Op.like]: `%${companyName.trim()}%`,
        },
        status: 'ACTIVE',
      },
    });

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

module.exports = { 
  saveSurvey, 
  getAllSurveys, 
  getSurveyById, 
  updateSurvey, 
  deleteSurvey,
  getSurveysByUserId,
  getSurveysByCompanyName
};
