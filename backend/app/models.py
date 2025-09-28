"""
Modelos SQLAlchemy para la base de datos
Define la estructura de las tablas y relaciones
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base
from pydantic import BaseModel
from typing import Optional

class IngestDataRequest(BaseModel):
    value: float
    timestamp: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "value": 2550.5,
                "timestamp": "2025-09-28T17:00:00"
            }
        }

class DataClassification(enum.Enum):
    """Enumeración para clasificación de datos"""
    valid = "valid"
    uncertain = "uncertain"
    quarantine = "quarantine"

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "erco_monitor"}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    location = Column(String(255))
    installed_capacity = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con dispositivos
    devices = relationship("Device", back_populates="project", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    __table_args__ = {"schema": "erco_monitor"}
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("erco_monitor.projects.id"), nullable=False)
    device_code = Column(String(100), nullable=False, unique=True)
    device_name = Column(String(255))
    nominal_power = Column(Float)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    project = relationship("Project", back_populates="devices")
    raw_records = relationship("RawRecord", back_populates="device", cascade="all, delete-orphan")
    valid_records = relationship("validRecord", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")

class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = {"schema": "erco_monitor"}
    
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("erco_monitor.devices.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    accumulated_value = Column(Float)
    delta_value = Column(Float)
    classification = Column(Enum(DataClassification))
    validation_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    device = relationship("Device", back_populates="raw_records")

class validRecord(Base):
    __tablename__ = "valid_records"
    __table_args__ = {"schema": "erco_monitor"}
    
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("erco_monitor.devices.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    accumulated_value = Column(Float)
    delta_value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    device = relationship("Device", back_populates="valid_records")

class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"schema": "erco_monitor"}
    
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("erco_monitor.devices.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="warning")
    message = Column(Text)
    details = Column(JSON)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    device = relationship("Device", back_populates="alerts")