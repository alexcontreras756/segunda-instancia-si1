import psycopg2
from config import Config

print("Probando conexión a la base de datos usando DATABASE_URL...")

try:
    conn = psycopg2.connect(Config.DATABASE_URL)
    print("SUCCESS: Conexion exitosa a la base de datos")
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1;")
    resultado = cursor.fetchone()
    print(f"Resultado de ejecutar SELECT 1: {resultado[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"ERROR al conectar: {e}")