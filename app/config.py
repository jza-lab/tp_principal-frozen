import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv(dotenv_path='credenciales.env') | load_dotenv(dotenv_path='.env')

class Config:

    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    BYPASS_LOGIN_CHECKS = os.getenv('BYPASS_LOGIN_CHECKS', 'False').lower() in ('true', '1', 't')

    # Configuraciones para desarrollo con PyScripter
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    TESTING = os.getenv('FLASK_TESTING', 'False').lower() in ('true', '1', 't')

    # Evitar problemas de puertos
    USE_RELOADER = DEBUG

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_COOKIE_PATH = '/'

    # Email Configuration for SMTP
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    # Email Configuration for 2FA Tokens
    TOKEN_MAIL_SERVER = os.getenv('TOKEN_MAIL_SERVER')
    TOKEN_MAIL_PORT = int(os.getenv('TOKEN_MAIL_PORT', 587))
    TOKEN_MAIL_USE_TLS = os.getenv('TOKEN_MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    TOKEN_MAIL_USERNAME = os.getenv('TOKEN_MAIL_USERNAME')
    TOKEN_MAIL_PASSWORD = os.getenv('TOKEN_MAIL_PASSWORD')
