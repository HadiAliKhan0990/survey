const Survey = require('./survey');
const Question = require('./question');
const { Association } = require('sequelize');
const Rating = require('./rating');
const User = require('./user');

const defineAssociations = () => {
  // survey and question relationship
  Survey.belongsToMany(Question, { through: 'SurveyQuestion' });
  Question.belongsToMany(Survey, { through: 'SurveyQuestion' });

  // Rating Model Association
  Rating.belongsTo(Question, { foreignKey: 'questionId', onDelete: 'CASCADE' });
  Question.hasMany(Rating, { foreignKey: 'questionId', onDelete: 'CASCADE' });

  Rating.belongsTo(User, { foreignKey: 'userId', onDelete: 'CASCADE' });
  User.hasMany(Rating, { foreignKey: 'userId', onDelete: 'CASCADE' });
};

module.exports = defineAssociations;
