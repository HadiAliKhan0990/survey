const express = require('express');
const router = express.Router();

const { verifyToken, requireAdmin } = require('../middlewares/authMiddleware');

const {
  getAllSurveys,
  saveSurvey,
  getSurveyById,
  updateSurvey,
  deleteSurvey,
  getSurveysByUserId,
  getSurveysByCompanyName
} = require('../controllers/surveyController');

const { surveyValidations } = require('../validations/survey');

// Public routes (no authentication required)
router.get('/public', getAllSurveys);
router.get('/public/company/:companyName', getSurveysByCompanyName);

// Admin only routes
router.get('/', verifyToken, requireAdmin, getAllSurveys);
router.get('/user/:userId', verifyToken, requireAdmin, getSurveysByUserId);
router.get('/company/:companyName', verifyToken, requireAdmin, getSurveysByCompanyName);
router.get('/:id', verifyToken, requireAdmin, getSurveyById);

router.post(
  '/',
  verifyToken,
  requireAdmin,
  surveyValidations,
  saveSurvey
);

router.put(
  '/:id',
  verifyToken,
  requireAdmin,
  surveyValidations,
  updateSurvey
);

router.delete('/:id', verifyToken, requireAdmin, deleteSurvey);

module.exports = router;
