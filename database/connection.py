import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """Obtener conexión a la base de datos"""
        if not Config.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL no está configurada. Asegúrate de configurar la variable de entorno "
                "DATABASE_URL en tu panel de Railway (ej. DATABASE_URL=${{Postgres.DATABASE_URL}}) "
                "o de definirla en el archivo .env local."
            )
        try:
            conn = psycopg2.connect(
                Config.DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            return conn
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    @contextmanager
    def get_cursor(self):
        """Context manager para manejar transacciones"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

db = DatabaseConnection()