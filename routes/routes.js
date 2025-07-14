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

app.use('/api/survey', surveyRoutes);

app.use('/api/question', questionRoutes);

app.use('/api/rating', ratingRoutes);

app.use('/api/stat', statRoutes);

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
