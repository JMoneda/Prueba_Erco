"""
Sistema de alertas en tiempo real
Detecta condiciones críticas y notifica via WebSocket
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from .models import Alert, RawRecord, Device, DataClassification
from .database import get_db

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Gestiona la detección y notificación de alertas
    """
    
    def __init__(self):
        self.websocket_clients = set()  # Clientes WebSocket conectados
        
    async def register_client(self, websocket):
        """Registra un nuevo cliente WebSocket"""
        self.websocket_clients.add(websocket)
        logger.info(f"WebSocket client registered. Total clients: {len(self.websocket_clients)}")
        
    async def unregister_client(self, websocket):
        """Desregistra un cliente WebSocket"""
        self.websocket_clients.discard(websocket)
        logger.info(f"WebSocket client unregistered. Total clients: {len(self.websocket_clients)}")
        
    async def broadcast_alert(self, alert_data: Dict):
        """
        Envía alerta a todos los clientes conectados
        """
        if self.websocket_clients:
            message = json.dumps(alert_data)
            # Crear lista de tareas de envío
            tasks = [client.send(message) for client in self.websocket_clients]
            # Enviar a todos simultáneamente
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Alert broadcasted to {len(self.websocket_clients)} clients")
    
    def check_alerts(self, device_id: int, db: Session) -> List[Alert]:
        """
        Verifica todas las condiciones de alerta para un dispositivo
        Retorna lista de alertas creadas
        """
        alerts_created = []
        
        # 1. Verificar registros consecutivos en cuarentena
        quarantine_alert = self._check_consecutive_quarantine(device_id, db)
        if quarantine_alert:
            alerts_created.append(quarantine_alert)
        
        # 2. Verificar delta negativo reciente
        negative_delta_alert = self._check_negative_delta(device_id, db)
        if negative_delta_alert:
            alerts_created.append(negative_delta_alert)
        
        # 3. Verificar valor congelado
        frozen_value_alert = self._check_frozen_value(device_id, db)
        if frozen_value_alert:
            alerts_created.append(frozen_value_alert)
        
        return alerts_created
    
    def _check_consecutive_quarantine(self, device_id: int, db: Session, threshold: int = 3) -> Optional[Alert]:
        """
        Verifica si hay 3 o más registros consecutivos en cuarentena
        """
        # Obtener últimos registros
        recent_records = db.query(RawRecord)\
            .filter(RawRecord.device_id == device_id)\
            .order_by(RawRecord.timestamp.desc())\
            .limit(threshold)\
            .all()
        
        if len(recent_records) >= threshold:
            # Verificar si todos están en cuarentena
            all_quarantine = all(r.classification == DataClassification.quarantine for r in recent_records)
            
            if all_quarantine:
                # Verificar si ya existe alerta no resuelta
                existing_alert = db.query(Alert)\
                    .filter(and_(
                        Alert.device_id == device_id,
                        Alert.alert_type == 'consecutive_quarantine',
                        Alert.resolved == False
                    ))\
                    .first()
                
                if not existing_alert:
                    # Crear nueva alerta
                    device = db.query(Device).filter(Device.id == device_id).first()
                    alert = Alert(
                        device_id=device_id,
                        alert_type='consecutive_quarantine',
                        severity='critical',
                        message=f"Dispositivo {device.device_code}: {threshold} registros consecutivos en cuarentena",
                        details={
                            'consecutive_count': threshold,
                            'timestamps': [r.timestamp.isoformat() for r in recent_records],
                            'reasons': [r.validation_reason for r in recent_records]
                        }
                    )
                    db.add(alert)
                    db.commit()
                    logger.warning(f"Alert created: Consecutive quarantine for device {device_id}")
                    return alert
        
        return None
    
    def _check_negative_delta(self, device_id: int, db: Session) -> Optional[Alert]:
        """
        Verifica si hay delta negativo en los últimos registros
        """
        # Buscar registros con delta negativo en la última hora
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        negative_records = db.query(RawRecord)\
            .filter(and_(
                RawRecord.device_id == device_id,
                RawRecord.delta_value < 0,
                RawRecord.timestamp >= one_hour_ago
            ))\
            .order_by(RawRecord.timestamp.desc())\
            .all()
        
        if negative_records:
            # Verificar si ya existe alerta reciente
            existing_alert = db.query(Alert)\
                .filter(and_(
                    Alert.device_id == device_id,
                    Alert.alert_type == 'negative_delta',
                    Alert.created_at >= one_hour_ago
                ))\
                .first()
            
            if not existing_alert:
                device = db.query(Device).filter(Device.id == device_id).first()
                alert = Alert(
                    device_id=device_id,
                    alert_type='negative_delta',
                    severity='critical',
                    message=f"Dispositivo {device.device_code}: Delta negativo detectado",
                    details={
                        'delta_values': [float(r.delta_value) for r in negative_records[:5]],
                        'timestamps': [r.timestamp.isoformat() for r in negative_records[:5]]
                    }
                )
                db.add(alert)
                db.commit()
                logger.warning(f"Alert created: Negative delta for device {device_id}")
                return alert
        
        return None
    
    def _check_frozen_value(self, device_id: int, db: Session) -> Optional[Alert]:
        """
        Verifica si el valor está congelado (sin cambios) por más de una hora
        """
        # Obtener últimos 5 registros
        recent_records = db.query(RawRecord)\
            .filter(RawRecord.device_id == device_id)\
            .order_by(RawRecord.timestamp.desc())\
            .limit(5)\
            .all()
        
        if len(recent_records) >= 5:
            # Verificar si todos tienen el mismo valor acumulado
            values = [r.accumulated_value for r in recent_records]
            if len(set(values)) == 1:  # Todos los valores son iguales
                # Calcular tiempo transcurrido
                time_diff = recent_records[0].timestamp - recent_records[-1].timestamp
                
                if time_diff >= timedelta(hours=1):
                    # Verificar que no sea horario nocturno
                    hour = recent_records[0].timestamp.hour
                    if 7 <= hour <= 17:  # Durante horario de generación
                        # Verificar alerta existente
                        existing_alert = db.query(Alert)\
                            .filter(and_(
                                Alert.device_id == device_id,
                                Alert.alert_type == 'frozen_value',
                                Alert.resolved == False
                            ))\
                            .first()
                        
                        if not existing_alert:
                            device = db.query(Device).filter(Device.id == device_id).first()
                            alert = Alert(
                                device_id=device_id,
                                alert_type='frozen_value',
                                severity='warning',
                                message=f"Dispositivo {device.device_code}: Valor congelado por más de {time_diff.total_seconds()/3600:.1f} horas",
                                details={
                                    'frozen_value': float(values[0]),
                                    'duration_hours': time_diff.total_seconds() / 3600,
                                    'start_time': recent_records[-1].timestamp.isoformat(),
                                    'end_time': recent_records[0].timestamp.isoformat()
                                }
                            )
                            db.add(alert)
                            db.commit()
                            logger.warning(f"Alert created: Frozen value for device {device_id}")
                            return alert
        
        return None
    
    def resolve_alerts(self, device_id: int, db: Session):
        """
        Resuelve alertas automáticamente cuando las condiciones mejoran
        """
        # Obtener alertas no resueltas del dispositivo
        unresolved_alerts = db.query(Alert)\
            .filter(and_(
                Alert.device_id == device_id,
                Alert.resolved == False
            ))\
            .all()
        
        for alert in unresolved_alerts:
            should_resolve = False
            
            if alert.alert_type == 'consecutive_quarantine':
                # Verificar si el último registro es válido
                last_record = db.query(RawRecord)\
                    .filter(RawRecord.device_id == device_id)\
                    .order_by(RawRecord.timestamp.desc())\
                    .first()
                    
                if last_record and last_record.classification == DataClassification.valid:
                    should_resolve = True
                    
            elif alert.alert_type == 'negative_delta':
                # Verificar si no hay deltas negativos recientes
                recent_negative = db.query(RawRecord)\
                    .filter(and_(
                        RawRecord.device_id == device_id,
                        RawRecord.delta_value < 0,
                        RawRecord.timestamp >= datetime.utcnow() - timedelta(hours=1)
                    ))\
                    .first()
                    
                if not recent_negative:
                    should_resolve = True
                    
            elif alert.alert_type == 'frozen_value':
                # Verificar si hay cambios en el valor
                recent_records = db.query(RawRecord)\
                    .filter(RawRecord.device_id == device_id)\
                    .order_by(RawRecord.timestamp.desc())\
                    .limit(3)\
                    .all()
                    
                if recent_records:
                    values = [r.accumulated_value for r in recent_records]
                    if len(set(values)) > 1:  # Hay diferentes valores
                        should_resolve = True
            
            if should_resolve:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                db.commit()
                logger.info(f"Alert resolved: {alert.alert_type} for device {device_id}")

# Instancia global del manager
alert_manager = AlertManager()