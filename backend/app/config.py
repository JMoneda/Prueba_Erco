"""
Configuración centralizada de la aplicación
Maneja todas las variables de entorno de forma segura
"""
import os
import secrets
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
# Busca el archivo .env en el directorio padre (raíz del proyecto)
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    """Configuración principal de la aplicación"""
    
    # Información de la aplicación
    APP_NAME: str = os.getenv("APP_NAME", "ERCO Energy Monitor")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Configuración de base de datos 
    # En producción, usar variables de entorno seguras o un gestor de secretos
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "erco_energy")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_SCHEMA: str = os.getenv("DB_SCHEMA", "erco_monitor")
    
    # validar que las credenciales críticas estén configuradas
    if not DB_PASSWORD:
        raise ValueError("DB_PASSWORD no está configurado. Por favor, configure la variable de entorno.")
    
    # Construir URL de base de datos
    DATABASE_URL: str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Configuración de seguridad
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "http://localhost").split(",")
    
    # Configuración de API
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "80"))
    
    # Configuración de validación
    TOLERANCE_PERCENTAGE: float = float(os.getenv("TOLERANCE_PERCENTAGE", "10"))
    quarantine_THRESHOLD: int = int(os.getenv("quarantine_THRESHOLD", "3"))
    
    # Configuración de simulación
    SIMULATION_ENABLED: bool = os.getenv("SIMULATION_ENABLED", "True").lower() == "true"
    SIMULATION_INTERVAL: int = int(os.getenv("SIMULATION_INTERVAL", "15"))  # minutos
    SIMULATION_DEVICES: int = int(os.getenv("SIMULATION_DEVICES", "10"))
    
    # Configuración de alertas
    ALERT_CHECK_INTERVAL: int = int(os.getenv("ALERT_CHECK_INTERVAL", "60"))  # segundos
         
    # Timezone
    TIMEZONE: str = os.getenv("TZ", "America/Bogota")
    
    @classmethod
    def validate_config(cls) -> bool:
        """valida que todas las configuraciones críticas estén presentes"""
        required_vars = [
            "DB_HOST", "DB_PORT", "DB_NAME", 
            "DB_USER", "DB_PASSWORD"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(
                f"Variables de entorno faltantes: {', '.join(missing_vars)}. "
                f"Por favor, configure estas variables en el archivo .env"
            )
        
        return True
    
    @classmethod
    def get_db_config(cls) -> dict:
        """Retorna configuración de base de datos como diccionario"""
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "database": cls.DB_NAME,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "schema": cls.DB_SCHEMA
        }
    
    @classmethod
    def is_production(cls) -> bool:
        """Verifica si está en modo producción"""
        return not cls.DEBUG
    
    @classmethod
    def log_config(cls):
        """Imprime configuración (sin datos sensibles)"""
        print("=" * 50)
        print(f"📱 {cls.APP_NAME} v{cls.APP_VERSION}")
        print("=" * 50)
        print(f"🔧 Modo: {'DEBUG' if cls.DEBUG else 'PRODUCCIÓN'}")
        print(f"🗄️  BD: {cls.DB_USER}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}")
        print(f"🌐 API: Puerto {cls.API_PORT}")
        print(f"🖥️  Frontend: Puerto {cls.FRONTEND_PORT}")
        print(f"🔄 Simulación: {'Habilitada' if cls.SIMULATION_ENABLED else 'Deshabilitada'}")
        print(f"⏰ Timezone: {cls.TIMEZONE}")
        print("=" * 50)

# Instancia global de configuración
config = Config()

# validar configuración al importar
try:
    config.validate_config()
except ValueError as e:
    print(f"❌ Error de configuración: {e}")
    raise