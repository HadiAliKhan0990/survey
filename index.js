require('./connection/db');
const dotenv = require('dotenv');
dotenv.config();

const express = require('express');
const cors = require('cors');
const app = express();

// Enable CORS for all origins (you can also restrict to specific origins)
app.use(cors());

// Optional: configure CORS options
/*
app.use(cors({
  origin: 'http://your-frontend-domain.com', // restrict to your frontend domain
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  credentials: true
}));
*/

//routes
require('./routes/routes');
