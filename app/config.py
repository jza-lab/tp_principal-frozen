import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv(dotenv_path='credenciales.env')


class Config:

    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Configuraciones para desarrollo con PyScripter
    DEBUG = True
    TESTING = False

    # Evitar problemas de puertos
    USE_RELOADER = False

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_COOKIE_CSRF_PROTECT = True
