const express = require('express');
const router = express.Router();

const { verifyToken, requireAdmin } = require('../middlewares/authMiddleware');

const {
  getAllSurveys,
  saveSurvey,
  getSurveyById,
  updateSurvey,
  deleteSurvey,
  getSurveysByUserId
} = require('../controllers/surveyController');

const { surveyValidations } = require('../validations/survey');

// Public routes (no authentication required)
router.get('/public', getAllSurveys);

// Admin only routes
router.get('/', verifyToken, requireAdmin, getAllSurveys);
router.get('/:id', verifyToken, requireAdmin, getSurveyById);
router.get('/user/:userId', verifyToken, requireAdmin, getSurveysByUserId);

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
