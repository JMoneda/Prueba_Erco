"""
Gestión de conexiones a base de datos
Implementa pool de conexiones y sesiones con configuración segura
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging
from .config import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO if not config.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# validar configuración de base de datos
if not config.DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurada correctamente")

# Crear engine con configuración optimizada
engine_config = {
    "pool_size": 20,
    "max_overflow": 10,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "echo": config.DEBUG,
    "connect_args": {
        "options": f"-csearch_path={config.DB_SCHEMA},public"
    }
}

try:
    engine = create_engine(config.DATABASE_URL, **engine_config)
    logger.info(f"✅ Conexión a base de datos configurada: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
except Exception as e:
    logger.error(f"❌ Error configurando conexión a base de datos: {e}")
    raise

# Crear sesión factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependencia de FastAPI para obtener sesión de base de datos
    Se usa con Depends() en los endpoints
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_context():
    """
    Context manager para uso fuera de FastAPI (tareas background, etc.)
    """
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def init_db():
    """
    Inicializa la base de datos
    Verifica conexión y esquema
    """
    try:
        # Verificar conexión
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"📊 PostgreSQL versión: {version}")
            
            # Verificar que el esquema existe
            result = conn.execute(
                text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{config.DB_SCHEMA}'")
            )
            if not result.fetchone():
                logger.warning(f"⚠️ Esquema '{config.DB_SCHEMA}' no existe. Creándolo...")
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {config.DB_SCHEMA}"))
                conn.commit()
            
            # Establecer search_path
            conn.execute(text(f"SET search_path TO {config.DB_SCHEMA}, public"))
            
        logger.info("✅ Base de datos inicializada correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        raise

def check_db_health():
    """
    Verifica el estado de la base de datos
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Error verificando salud de BD: {e}")
        return False

def get_db_stats():
    """
    Obtiene estadísticas de la base de datos
    """
    try:
        with engine.connect() as conn:
            stats = {}
            
            queries = {
                "total_devices": f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.devices",
                "active_devices": f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.devices WHERE status = 'active'",
                "total_records": f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.raw_records",
                "valid_records": f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.raw_records WHERE classification = 'valid'",
                "active_alerts": f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.alerts WHERE resolved = false"
            }
            
            for key, query in queries.items():
                result = conn.execute(text(query))
                stats[key] = result.scalar()
            
            return stats
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return {}