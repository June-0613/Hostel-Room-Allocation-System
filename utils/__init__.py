# __init__.py

from flask import Flask
from flask_mail import Mail
from flask_mysqldb import MySQL

mail = Mail()
mysql = MySQL()

def create_app():
    app = Flask(__name__)

    # Configurations
    app.config['SECRET_KEY'] = 'your_secret_key_here'
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
    app.config['MAIL_PASSWORD'] = 'your_app_password'

    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = 'DDkavitha@36'
    app.config['MYSQL_DB'] = 'hostel_management'

    # Initialize extensions
    mail.init_app(app)
    mysql.init_app(app)

    # Import routes and register (if using blueprints)
    from . import routes
    app.register_blueprint(routes.main)

    return app
