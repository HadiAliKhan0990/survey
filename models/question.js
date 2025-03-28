const { DataTypes } = require('sequelize');
const sequelize = require('../config/database');

const Questions = sequelize.define(
  'Questions',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    text: {
      type: DataTypes.STRING,
      allowNull: false,
    },
  },
  {
    tableName: 'questions',
    timestamps: true,
  }
);

module.exports = Questions;
