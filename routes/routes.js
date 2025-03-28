const { authMiddleware } = require('../middlewares/auth');
const authRoutes = require('./authRoutes');
const surveyRoutes = require('./surveyRoutes');
const questionRoutes = require('./questionRoutes');
const ratingRoutes = require('./ratingRoutes');
const statRoutes = require('./statRoutes');

const express = require('express');

const app = express();

// Middleware to parse JSON
app.use(express.json());

// test routes to check if server is running
app.get('/api/test', (req, res) => {
  res.status(200).json({ message: 'API is working!' });
});

// app routes protected test
app.get('/api/', authMiddleware, (req, res) => {
  res.status(200).json({ message: 'Protected API is working!' });
});

app.use('/api/auth', authRoutes);

app.use('/api/survey', authMiddleware, surveyRoutes);

app.use('/api/question', authMiddleware, questionRoutes);

app.use('/api/rating', authMiddleware, ratingRoutes);

app.use('/api/stat', authMiddleware, statRoutes);

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
