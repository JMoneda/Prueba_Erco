"""
Módulo de validación de datos
Implementa la lógica de clasificación según reglas de negocio
"""
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from .models import RawRecord, validRecord, Device, DataClassification
from .config import config

logger = logging.getLogger(__name__)

class Datavalidator:
    """
    Clase principal para validación de datos de energía
    Clasifica los datos en: válido, incierto o cuarentena
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.tolerance = config.TOLERANCE_PERCENTAGE / 100  # Convertir a decimal
        
    def validate_record(self, 
                       device_id: int, 
                       timestamp: datetime, 
                       accumulated_value: float) -> Tuple[DataClassification, str, Optional[float]]:
        """
        valida un registro comparándolo con histórico y reglas de negocio
        
        Returns:
            Tuple de (clasificación, razón, delta_value)
        """
        # Obtener registro anterior del dispositivo
        previous_record = self._get_previous_record(device_id, timestamp)
        
        # Calcular delta
        delta_value = None
        if previous_record:
            delta_value = accumulated_value - previous_record.accumulated_value
            time_diff = (timestamp - previous_record.timestamp).total_seconds() / 3600  # horas
            
            # validación 1: Delta negativo (falla severa)
            if delta_value < 0:
                return DataClassification.quarantine, "Delta negativo detectado - posible falla del inversor", delta_value
            
            # validación 2: Valor congelado (misma lectura)
            if delta_value == 0 and time_diff >= 1:  # Más de 1 hora sin cambios
                if self._is_nighttime(timestamp):
                    # Es normal no generar de noche
                    return DataClassification.valid, "Sin generación nocturna", delta_value
                else:
                    return DataClassification.quarantine, "Valor congelado durante período de generación", delta_value
        
        # validación 3: Comparar con histórico
        if delta_value is not None:
            historical_stats = self._get_historical_stats(device_id, timestamp.hour)
            
            if historical_stats and historical_stats['avg_delta']:
                avg_delta = historical_stats['avg_delta']
                std_delta = historical_stats['std_delta'] or avg_delta * 0.1  # 10% si no hay std
                
                # Calcular límites con tolerancia
                lower_bound = avg_delta - (std_delta * 2)  # 2 desviaciones estándar
                upper_bound = avg_delta + (std_delta * 2)
                
                # Ajustar tolerancia según configuración
                tolerance_adjustment = avg_delta * self.tolerance
                lower_bound -= tolerance_adjustment
                upper_bound += tolerance_adjustment
                
                # Clasificar según límites
                if lower_bound <= delta_value <= upper_bound:
                    return DataClassification.valid, "Dentro de rangos históricos normales", delta_value
                elif delta_value > upper_bound * 1.5:  # Salto atípico severo
                    return DataClassification.quarantine, f"Salto atípico: {delta_value:.2f} vs esperado {avg_delta:.2f}", delta_value
                else:
                    return DataClassification.uncertain, f"Fuera de rango normal: {delta_value:.2f} vs esperado {avg_delta:.2f}", delta_value
            else:
                # Sin histórico suficiente, ser más permisivo
                if delta_value > 0 and delta_value < 100:  # Límites razonables
                    return DataClassification.valid, "Sin histórico - valor razonable", delta_value
                else:
                    return DataClassification.uncertain, "Sin histórico - valor requiere revisión", delta_value
        
        # Primer registro del dispositivo
        if accumulated_value >= 0:
            return DataClassification.valid, "Primer registro del dispositivo", 0
        else:
            return DataClassification.quarantine, "Valor inicial negativo", 0
    
    def _get_previous_record(self, device_id: int, timestamp: datetime) -> Optional[RawRecord]:
        """Obtiene el registro anterior más cercano del dispositivo"""
        return self.db.query(RawRecord)\
            .filter(RawRecord.device_id == device_id)\
            .filter(RawRecord.timestamp < timestamp)\
            .order_by(RawRecord.timestamp.desc())\
            .first()
    
    def _get_historical_stats(self, device_id: int, hour: int) -> dict:
        """
        Obtiene estadísticas históricas del dispositivo para una hora específica
        Usa la vista materializada para mejor performance
        """
        query = text("""
            SELECT avg_delta, std_delta, min_delta, max_delta, sample_count
            FROM erco_monitor.mv_device_hourly_stats
            WHERE device_id = :device_id AND hour_of_day = :hour
        """)
    
        result = self.db.execute(query, {"device_id": device_id, "hour": hour}).fetchone()
        
        if result:
            return {
                'avg_delta': result[0],
                'std_delta': result[1],
                'min_delta': result[2],
                'max_delta': result[3],
                'sample_count': result[4]
            }
        return {}
    
    def _is_nighttime(self, timestamp: datetime) -> bool:
        """Determina si es horario nocturno (sin generación solar)"""
        hour = timestamp.hour
        return hour < 6 or hour >= 19  # Fuera de 6am-7pm
    
    def process_and_store(self, device_id: int, timestamp: datetime, accumulated_value: float) -> RawRecord:
        """
        Procesa un nuevo registro: valida, clasifica y almacena
        """
        # validar el registro
        classification, reason, delta_value = self.validate_record(device_id, timestamp, accumulated_value)
        
        # Guardar en registros crudos (auditoría completa)
        raw_record = RawRecord(
            device_id=device_id,
            timestamp=timestamp,
            accumulated_value=accumulated_value,
            delta_value=delta_value,
            classification=classification,
            validation_reason=reason
        )
        self.db.add(raw_record)
        
        # Si es válido, también guardar en tabla de válidos
        if classification == DataClassification.valid:
            valid_record = validRecord(
                device_id=device_id,
                timestamp=timestamp,
                accumulated_value=accumulated_value,
                delta_value=delta_value
            )
            self.db.add(valid_record)
        
        self.db.commit()
        
        logger.info(f"Processed record for device {device_id}: {classification.value} - {reason}")
        return raw_record
    
    def check_consecutive_quarantine(self, device_id: int, limit: int = 3) -> bool:
        """
        Verifica si hay registros consecutivos en cuarentena
        """
        recent_records = self.db.query(RawRecord)\
            .filter(RawRecord.device_id == device_id)\
            .order_by(RawRecord.timestamp.desc())\
            .limit(limit)\
            .all()
        
        if len(recent_records) >= limit:
            return all(r.classification == DataClassification.quarantine for r in recent_records)
        return False