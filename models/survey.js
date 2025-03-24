const { DataTypes } = require('sequelize');
const sequelize = require('../config/database');

const Survey = sequelize.define(
  'Survey',
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    name: {
      type: DataTypes.STRING,
      allowNull: false,
    },
    heading: {
      type: DataTypes.STRING,
      allowNull: false,
    },
  },
  {
    tableName: 'survey',
    timestamps: true,
  }
);

module.exports = Survey;
