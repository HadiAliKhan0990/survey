const sequelize = require('../config/database');

sequelize
  .authenticate()
  .then(() => console.log('Database connected...'))
  .catch((err) => console.log('Error connecting to database:', err));

sequelize
  .sync({ alter: true })
  .then(() => console.log('Database synchronized with models'))
  .catch((err) => console.error('Error synchronizing database:', err));
