"""
API principal con FastAPI
Expone endpoints REST y WebSocket para el sistema de monitoreo
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text  # ← IMPORTANTE: Importar text aquí
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio
import logging

from .config import config
from .database import get_db, init_db, SessionLocal
from .models import Device, Project, RawRecord, Alert, DataClassification
from .validators import Datavalidator
from .simulator import SolarDataSimulator
from .alerts import alert_manager
from .models import IngestDataRequest

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    logger.info("Starting ERCO Energy Monitor API")
    init_db()
    
    # Iniciar tarea de simulación en background
    if config.SIMULATION_ENABLED:
        asyncio.create_task(simulation_task())
    
    # Actualizar vista materializada periódicamente
    asyncio.create_task(refresh_materialized_view())
    
    yield
    
    # Shutdown
    logger.info("Shutting down ERCO Energy Monitor API")

# Crear aplicación FastAPI
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, usar config.CORS_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== ENDPOINTS ==============

@app.get("/")
async def root():
    """Endpoint de salud"""
    return {
        "status": "online",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/projects")
async def get_projects(db: Session = Depends(get_db)):
    """Obtener todos los proyectos"""
    try:
        projects = db.query(Project).all()
        return [{
            "id": p.id,
            "name": p.name,
            "location": p.location,
            "installed_capacity": float(p.installed_capacity) if p.installed_capacity else 0,
            "device_count": len(p.devices)
        } for p in projects]
    except Exception as e:
        logger.error(f"Error obteniendo proyectos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
async def get_devices(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener dispositivos con filtros opcionales"""
    try:
        query = db.query(Device)
        
        if project_id:
            query = query.filter(Device.project_id == project_id)
        if status:
            query = query.filter(Device.status == status)
        
        devices = query.all()
        return [{
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "project_name": d.project.name,
            "status": d.status,
            "nominal_power": float(d.nominal_power) if d.nominal_power else 0
        } for d in devices]
    except Exception as e:
        logger.error(f"Error obteniendo dispositivos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices/{device_id}/status")
async def get_device_status(device_id: int, db: Session = Depends(get_db)):
    """Obtener estado actual de un dispositivo"""
    try:
        # IMPORTANTE: Usar text() para envolver la consulta SQL
        query_str = f"""
            SELECT * FROM {config.DB_SCHEMA}.v_device_current_status
            WHERE device_id = :device_id
        """
        
        result = db.execute(text(query_str), {"device_id": device_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Device not found")
        
        return {
            "device_id": result[0],
            "device_code": result[1],
            "device_name": result[2],
            "project_name": result[3],
            "last_reading": result[4].isoformat() if result[4] else None,
            "accumulated_value": float(result[5]) if result[5] else None,
            "delta_value": float(result[6]) if result[6] else None,
            "classification": result[7],
            "status": result[8]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estado del dispositivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices/{device_id}/records")
async def get_device_records(
    device_id: int,
    hours: int = 24,
    classification: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtener registros históricos de un dispositivo"""
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        query = db.query(RawRecord)\
            .filter(RawRecord.device_id == device_id)\
            .filter(RawRecord.timestamp >= since)
        
        if classification:
            # CORRECCIÓN: Mapear los valores correctamente
            classification_map = {
                'valid': DataClassification.valid,
                'uncertain': DataClassification.uncertain, 
                'quarantine': DataClassification.quarantine
            }
            
            if classification.lower() in classification_map:
                query = query.filter(RawRecord.classification == classification_map[classification.lower()])
            else:
                raise HTTPException(status_code=400, detail=f"Invalid classification: {classification}")
        
        records = query.order_by(RawRecord.timestamp.desc()).limit(100).all()
        
        return [{
            "timestamp": r.timestamp.isoformat(),
            "accumulated_value": float(r.accumulated_value) if r.accumulated_value else None,
            "delta_value": float(r.delta_value) if r.delta_value else None,
            "classification": r.classification.value if r.classification else None,
            "validation_reason": r.validation_reason
        } for r in records]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo registros: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/devices/{device_id}/ingest")
async def ingest_data(
    device_id: int,
    data: IngestDataRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para ingesta manual de datos
    Procesa, valida y almacena el registro
    """
    try:
        # Extraer valores del modelo Pydantic
        value = data.value
        timestamp_str = data.timestamp
                
        # Verificar que el dispositivo existe
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Parsear timestamp si se proporciona
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Procesar y validar
        validator = Datavalidator(db)
        record = validator.process_and_store(device_id, timestamp, float(value))
        
        # Verificar alertas
        alerts = alert_manager.check_alerts(device_id, db)
        
        # Enviar alertas via WebSocket si hay nuevas
        for alert in alerts:
            await alert_manager.broadcast_alert({
                "id": alert.id,
                "device_code": device.device_code,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.created_at.isoformat()
            })
        
        return {
            "success": True,
            "record": {
                "timestamp": record.timestamp.isoformat(),
                "value": float(record.accumulated_value) if record.accumulated_value else None,
                "delta": float(record.delta_value) if record.delta_value else None,
                "classification": record.classification.value if record.classification else None,
                "reason": record.validation_reason
            },
            "alerts_triggered": len(alerts)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en ingesta de datos: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
async def get_alerts(
    device_id: Optional[int] = None,
    resolved: Optional[bool] = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Obtener alertas con filtros"""
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        query = db.query(Alert).filter(Alert.created_at >= since)
        
        if device_id:
            query = query.filter(Alert.device_id == device_id)
        if resolved is not None:
            query = query.filter(Alert.resolved == resolved)
        
        alerts = query.order_by(Alert.created_at.desc()).all()
        
        return [{
            "id": a.id,
            "device_id": a.device_id,
            "device_code": a.device.device_code,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "details": a.details,
            "resolved": a.resolved,
            "created_at": a.created_at.isoformat(),
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None
        } for a in alerts]
    except Exception as e:
        logger.error(f"Error obteniendo alertas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """Resolver una alerta manualmente"""
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "Alert resolved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolviendo alerta: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics/quality")
async def get_quality_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas de calidad de datos"""
    try:
        # IMPORTANTE: Usar text() para envolver la consulta SQL
        query_str = f"SELECT * FROM {config.DB_SCHEMA}.v_data_quality_summary"
        results = db.execute(text(query_str)).fetchall()
        
        return [{
            "device_code": r[0],
            "valid_count": r[1],
            "uncertain_count": r[2],
            "quarantine_count": r[3],
            "total_count": r[4],
            "validity_percentage": float(r[5]) if r[5] else 0
        } for r in results]
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Verificación de salud del sistema"""
    try:
        # Verificar conexión a BD
        db.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ============== WEBSOCKET ==============

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket para alertas en tiempo real
    """
    await websocket.accept()
    await alert_manager.register_client(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await alert_manager.unregister_client(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await alert_manager.unregister_client(websocket)

# ============== TAREAS BACKGROUND ==============

async def simulation_task():
    """
    Tarea de simulación que corre en background
    """
    await asyncio.sleep(10)  # Esperar inicio completo
    
    while True:
        db = None
        try:
            # Crear sesión para tarea background
            db = SessionLocal()
            
            # Verificar si hay dispositivos
            devices = db.query(Device).filter(Device.status == 'active').all()
            
            if devices:
                simulator = SolarDataSimulator(db)
                timestamp = datetime.utcnow()
                
                # Solo simular durante horas de sol (6am - 6pm)
                if 6 <= timestamp.hour <= 18:
                    results = simulator.simulate_batch(timestamp, devices)
                    
                    # Verificar alertas para cada dispositivo
                    for device in devices:
                        alerts = alert_manager.check_alerts(device.id, db)
                        
                        # Broadcast alertas nuevas
                        for alert in alerts:
                            await alert_manager.broadcast_alert({
                                "id": alert.id,
                                "device_code": device.device_code,
                                "alert_type": alert.alert_type,
                                "severity": alert.severity,
                                "message": alert.message,
                                "timestamp": alert.created_at.isoformat()
                            })
                    
                    logger.info(f"Simulation batch completed: {len(results)} records")
            else:
                logger.warning("No active devices found for simulation")
                
        except Exception as e:
            logger.error(f"Error in simulation task: {e}")
        finally:
            if db:
                db.close()
        
        # Esperar hasta próximo intervalo (15 minutos por defecto)
        await asyncio.sleep(config.SIMULATION_INTERVAL * 60)

async def refresh_materialized_view():
    """
    Actualiza la vista materializada de estadísticas
    """
    await asyncio.sleep(30)  # Esperar inicio completo
    
    while True:
        db = None
        try:
            db = SessionLocal()
            # IMPORTANTE: Usar text() para la consulta SQL
            query_str = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {config.DB_SCHEMA}.mv_device_hourly_stats"
            db.execute(text(query_str))
            db.commit()
            logger.info("Materialized view refreshed successfully")
        except Exception as e:
            logger.error(f"Error refreshing materialized view: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
        
        # Actualizar cada hora
        await asyncio.sleep(3600)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=config.DEBUG)