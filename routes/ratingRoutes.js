const express = require('express');
const { verifyToken } = require('../middlewares/authMiddleware');

const { 
  saveRating, 
  updateRating, 
  getRatingById, 
  getRatingsByQuestion, 
  getRatingsByUser,
  deleteRating,
  getAllRatings
} = require('../controllers/ratingController');

const { ratingValidation } = require('../validations/rating');

const router = express.Router();

// Public routes (no authentication required)
router.post('/public', ratingValidation, saveRating);
router.get('/public/question/:question_id', getRatingsByQuestion);

// Protected routes (authentication required)
router.post('/', verifyToken, ratingValidation, saveRating);
router.put('/:ratingId', verifyToken, ratingValidation, updateRating);
router.get('/:ratingId', verifyToken, getRatingById);
router.get('/question/:questionId', verifyToken, getRatingsByQuestion);
router.get('/user/:userId', verifyToken, getRatingsByUser);
router.delete('/:ratingId', verifyToken, deleteRating);

module.exports = router;
