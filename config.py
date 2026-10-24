import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'criss-default-dev-secret-key-3nf-college')
    
    # MySQL Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3308'))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'criss_db')
    MYSQL_POOL_SIZE = int(os.getenv('MYSQL_POOL_SIZE', '5'))

    # Security settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

    # Application settings
    MAX_OVERDUE_FINE_PER_DAY = 1.00 # $1.00 or INR 10.00
    MAX_SIMULTANEOUS_LOANS = 3
    RESERVATION_EXPIRY_HOURS = 24
