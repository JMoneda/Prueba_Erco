-- Esquema de base de datos para ERCO Energy Monitor
-- Autor: JMGH
-- Fecha: 2025
-- Compatible con PostgreSQL 17

-- Crear esquema
CREATE SCHEMA IF NOT EXISTS erco_monitor;
SET search_path TO erco_monitor;

-- Tabla de proyectos
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    location VARCHAR(255),
    installed_capacity DECIMAL(10,2), -- kW
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de dispositivos (inversores)
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    device_code VARCHAR(100) NOT NULL UNIQUE,
    device_name VARCHAR(255),
    nominal_power DECIMAL(10,2), -- kW nominal del inversor
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, maintenance
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para devices
CREATE INDEX IF NOT EXISTS idx_device_project ON devices(project_id);
CREATE INDEX IF NOT EXISTS idx_device_code ON devices(device_code);

-- Tipo ENUM para clasificación de datos
DO $$ BEGIN
    CREATE TYPE data_classification AS ENUM ('valid', 'uncertain', 'quarantine');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Tabla de registros crudos (todos los datos)
CREATE TABLE IF NOT EXISTS raw_records (
    id SERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    accumulated_value DECIMAL(15,3), -- kWh acumulado
    delta_value DECIMAL(10,3), -- Diferencia con registro anterior
    classification data_classification,
    validation_reason TEXT, -- Razón de la clasificación
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, timestamp) -- No duplicados por dispositivo/tiempo
);

-- Índices para raw_records
CREATE INDEX IF NOT EXISTS idx_raw_device_time ON raw_records(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_raw_classification ON raw_records(classification);

-- Tabla de registros válidos (solo datos validados)
CREATE TABLE IF NOT EXISTS valid_records (
    id SERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    accumulated_value DECIMAL(15,3),
    delta_value DECIMAL(10,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, timestamp)
);

-- Índices para valid_records
CREATE INDEX IF NOT EXISTS idx_valid_device_time ON valid_records(device_id, timestamp DESC);

-- Tabla de estadísticas históricas por dispositivo y franja horaria
CREATE TABLE IF NOT EXISTS device_statistics (
    id SERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day >= 0 AND hour_of_day < 24),
    avg_delta DECIMAL(10,3), -- Promedio de generación en esa hora
    std_delta DECIMAL(10,3), -- Desviación estándar
    min_delta DECIMAL(10,3),
    max_delta DECIMAL(10,3),
    sample_count INTEGER,
    last_updated DATE,
    UNIQUE(device_id, hour_of_day)
);

-- Índices para device_statistics
CREATE INDEX IF NOT EXISTS idx_stats_device_hour ON device_statistics(device_id, hour_of_day);

-- Tabla de alertas
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL, -- 'consecutive_quarantine', 'negative_delta', 'frozen_value'
    severity VARCHAR(20) DEFAULT 'warning', -- info, warning, critical
    message TEXT,
    details JSONB, -- Información adicional en JSON
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para alerts
CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON alerts(resolved, created_at DESC) WHERE resolved = FALSE;

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para actualizar updated_at
DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at 
    BEFORE UPDATE ON projects
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;
CREATE TRIGGER update_devices_updated_at 
    BEFORE UPDATE ON devices
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at();

-- Comentarios en las tablas para documentación
COMMENT ON TABLE projects IS 'Proyectos o plantas solares monitoreadas';
COMMENT ON TABLE devices IS 'Dispositivos inversores asociados a cada proyecto';
COMMENT ON TABLE raw_records IS 'Tabla de auditoría con todos los registros recibidos';
COMMENT ON TABLE valid_records IS 'Solo registros que pasaron la validación';
COMMENT ON TABLE alerts IS 'Alertas generadas por el sistema de monitoreo';
COMMENT ON TABLE device_statistics IS 'Estadísticas históricas para validación';

COMMENT ON COLUMN raw_records.classification IS 'Clasificación del registro: valid, uncertain, quarantine';
COMMENT ON COLUMN raw_records.delta_value IS 'Diferencia con el registro anterior (generación en el período)';
COMMENT ON COLUMN devices.nominal_power IS 'Potencia nominal del inversor en kW';