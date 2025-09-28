"""
Simulador de datos de inversores solares
Genera datos realistas con errores intencionales para pruebas
"""
import numpy as np
import random
from datetime import datetime, timedelta
import logging
from typing import List, Dict
from sqlalchemy.orm import Session
from .models import Device, Project
from .validators import Datavalidator

logger = logging.getLogger(__name__)

class SolarDataSimulator:
    """
    Simula la generación de energía solar con comportamiento realista
    Incluye variabilidad natural y errores intencionales
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.validator = Datavalidator(db_session)
        self.device_states = {}  # Estado acumulado por dispositivo
        
    def solar_profile(self, hour: float) -> float:
        """
        Perfil de generación solar usando función sinusoidal
        Simula la curva típica de generación durante el día
        """
        if 6 <= hour <= 18:
            # Mapear hora a radianes para función seno
            x = (hour - 6) / 12 * np.pi
            return np.sin(x)
        else:
            return 0.0
    
    def generate_device_data(self, 
                           device_id: int, 
                           timestamp: datetime, 
                           error_probability: float = 0.1) -> float:
        """
        Genera dato de energía acumulada para un dispositivo
        
        Args:
            device_id: ID del dispositivo
            timestamp: Momento de la lectura
            error_probability: Probabilidad de introducir error (0-1)
        """
        # Obtener estado actual del dispositivo
        if device_id not in self.device_states:
            # Inicializar con valor base aleatorio
            self.device_states[device_id] = {
                'accumulated': random.uniform(1000, 5000),
                'last_timestamp': timestamp - timedelta(minutes=15),
                'frozen_count': 0,
                'efficiency': random.uniform(0.85, 0.98)  # Eficiencia del inversor
            }
        
        state = self.device_states[device_id]
        hour = timestamp.hour + timestamp.minute / 60
        
        # Calcular generación base según perfil solar
        base_generation = self.solar_profile(hour)
        
        # Aplicar variabilidad natural
        weather_factor = random.uniform(0.7, 1.0)  # Nubes, etc.
        device_efficiency = state['efficiency']
        
        # Calcular incremento (kWh en 15 minutos)
        time_delta = (timestamp - state['last_timestamp']).seconds / 3600
        nominal_power = 50  # kW nominal del inversor
        increment = base_generation * weather_factor * device_efficiency * nominal_power * time_delta
        
        # Introducir errores intencionales
        if random.random() < error_probability:
            error_type = random.choice(['negative_delta', 'frozen', 'spike', 'zero'])
            
            if error_type == 'negative_delta':
                # Delta negativo (falla del inversor)
                increment = -random.uniform(10, 50)
                logger.warning(f"Injected negative delta for device {device_id}")
                
            elif error_type == 'frozen':
                # Valor congelado
                increment = 0
                state['frozen_count'] += 1
                logger.warning(f"Injected frozen value for device {device_id} (count: {state['frozen_count']})")
                
            elif error_type == 'spike':
                # Salto atípico
                increment *= random.uniform(3, 5)
                logger.warning(f"Injected spike for device {device_id}")
                
            elif error_type == 'zero':
                # Lectura cero durante período de generación
                if 8 <= hour <= 16:
                    increment = 0
                    logger.warning(f"Injected zero generation during daytime for device {device_id}")
        else:
            state['frozen_count'] = 0  # Reset frozen counter
        
        # Actualizar valor acumulado
        new_value = state['accumulated'] + increment
        state['accumulated'] = new_value
        state['last_timestamp'] = timestamp
        
        return max(0, new_value)  # Evitar valores negativos totales
    
    def simulate_batch(self, timestamp: datetime, devices: List[Device]) -> List[Dict]:
        """
        Simula datos para múltiples dispositivos en un momento dado
        """
        results = []
        
        for device in devices:
            try:
                # Generar valor con 10% de probabilidad de error
                accumulated_value = self.generate_device_data(
                    device.id, 
                    timestamp, 
                    error_probability=0.1
                )
                
                # Procesar y validar el registro
                record = self.validator.process_and_store(
                    device.id,
                    timestamp,
                    accumulated_value
                )
                
                results.append({
                    'device_id': device.id,
                    'device_code': device.device_code,
                    'timestamp': timestamp,
                    'value': accumulated_value,
                    'classification': record.classification.value,
                    'reason': record.validation_reason
                })
                
            except Exception as e:
                logger.error(f"Error simulating data for device {device.id}: {e}")
                
        return results
    
    def run_simulation(self, 
                      start_date: datetime, 
                      end_date: datetime, 
                      interval_minutes: int = 15):
        """
        Ejecuta simulación completa para un período de tiempo
        """
        logger.info(f"Starting simulation from {start_date} to {end_date}")
        
        # Obtener todos los dispositivos activos
        devices = self.db.query(Device).filter(Device.status == 'active').all()
        
        if not devices:
            logger.warning("No active devices found for simulation")
            return
        
        current_time = start_date
        total_records = 0
        
        while current_time <= end_date:
            # Solo simular durante horas de generación solar (6am - 7pm)
            if 6 <= current_time.hour <= 18:
                batch_results = self.simulate_batch(current_time, devices)
                total_records += len(batch_results)
                
                # Log resumen cada hora
                if current_time.minute == 0:
                    valid_count = sum(1 for r in batch_results if r['classification'] == 'valid')
                    logger.info(f"Simulated {len(batch_results)} records at {current_time} - {valid_count} valid")
            
            current_time += timedelta(minutes=interval_minutes)