import os
import MySQLdb

class Config:
    SECRET_KEY = 'hostel_management@0613'

    # Flask-Mail settings example
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_DEFAULT_SENDER= ('Hostel Management', 'juneelora6@gmail.com')  # or a name-email pair: ('Your App Name', 'youremail@gmail.com')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    SECURITY_PASSWORD_SALT = 'your-secret-salt'
    # DB config example
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'DDkavitha@36'
    MYSQL_DB = 'hostel_management'

def get_connection():
    return MySQLdb.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        passwd=Config.MYSQL_PASSWORD,
        db=Config.MYSQL_DB
    )
