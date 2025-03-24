const { DataTypes } = require('sequelize');
const sequelize = require('../config/database');
const Question = require('./question');
const User = require('./user');

const Rating = sequelize.define(
  'Rating',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    rating: {
      type: DataTypes.INTEGER,
      allowNull: false,
      validate: {
        min: 1,
        max: 5,
      },
    },
    userId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'users', // Matches User model table name
        key: 'id',
      },
      onDelete: 'CASCADE',
    },
    questionId: {
      type: DataTypes.UUID,
      allowNull: false,
      references: {
        model: 'questions', // Matches Question model table name
        key: 'id',
      },
      onDelete: 'CASCADE',
    },
  },
  {
    tableName: 'ratings',
    timestamps: true,
  }
);

module.exports = Rating;
