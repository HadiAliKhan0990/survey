// const { DataTypes } = require('sequelize');
// const sequelize = require('../config/database');
// const Survey = require('./survey');
// const Question = require('./question');

// const SurveyQuestion = sequelize.define(
//   'SurveyQuestion',
//   {
//     id: {
//       type: DataTypes.UUID,
//       defaultValue: DataTypes.UUIDV4,
//       primaryKey: true,
//     },
//   },
//   {
//     tableName: 'survey_questions',
//     timestamps: true,
//   }
// );

// Survey.belongsToMany(Question, { through: SurveyQuestion });
// Question.belongsToMany(Survey, { through: SurveyQuestion });

// module.exports = SurveyQuestion;
