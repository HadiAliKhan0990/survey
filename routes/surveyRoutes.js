const express = require('express');
const router = express.Router();

const { authorizeMiddleware } = require('../middlewares/authorize');

const roles = require('../utils/role');

const {
  getAllSurveys,
  saveSurvey,
} = require('../controllers/surveyController');

const { surveyValidations } = require('../validations/survey');

router.get('/', authorizeMiddleware([roles.Admin]), getAllSurveys);

router.post(
  '/',
  authorizeMiddleware([roles.Admin]),
  surveyValidations,
  saveSurvey
);

module.exports = router;
