import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL no está configurada. Asegúrate de configurar la variable de entorno "
            "DATABASE_URL en tu panel de Railway (ej. DATABASE_URL=${{Postgres.DATABASE_URL}}) "
            "o de definirla en el archivo .env local."
        )
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False

class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}