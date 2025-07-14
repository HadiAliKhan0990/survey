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
      type: DataTypes.TEXT,
      allowNull: false,
    },
    survey_id: {
      type: DataTypes.UUID,
      allowNull: false,
    },
    status: {
      type: DataTypes.ENUM('ACTIVE', 'PENDING', 'DE_ACTIVE'),
      defaultValue: 'ACTIVE',
    },
  },
  {
    tableName: 'questions',
    timestamps: true,
    createdAt: 'created_at',
    updatedAt: 'updated_at',
  }
);

module.exports = Questions;
