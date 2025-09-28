-- Vistas y vistas materializadas para ERCO Energy Monitor
-- Compatible con PostgreSQL 17

SET search_path TO erco_monitor;

-- Eliminar vista materializada si existe para recrearla
DROP MATERIALIZED VIEW IF EXISTS mv_device_hourly_stats CASCADE;

-- Vista materializada para estadísticas históricas de los últimos 7 días
CREATE MATERIALIZED VIEW mv_device_hourly_stats AS
WITH recent_data AS (
    SELECT 
        device_id,
        EXTRACT(HOUR FROM timestamp) as hour_of_day,
        delta_value,
        timestamp::date as record_date
    FROM valid_records
    WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
        AND delta_value IS NOT NULL
        AND delta_value > 0
)
SELECT 
    device_id,
    hour_of_day::INTEGER,
    AVG(delta_value)::DECIMAL(10,3) as avg_delta,
    STDDEV(delta_value)::DECIMAL(10,3) as std_delta,
    MIN(delta_value)::DECIMAL(10,3) as min_delta,
    MAX(delta_value)::DECIMAL(10,3) as max_delta,
    COUNT(*)::INTEGER as sample_count,
    MAX(record_date) as last_date
FROM recent_data
GROUP BY device_id, hour_of_day;

-- Índice único para permitir REFRESH CONCURRENTLY
CREATE UNIQUE INDEX idx_mv_device_hourly ON mv_device_hourly_stats(device_id, hour_of_day);

-- Comentario sobre la vista materializada
COMMENT ON MATERIALIZED VIEW mv_device_hourly_stats IS 'Estadísticas por hora de los últimos 7 días para validación';

-- Vista para monitoreo en tiempo real
CREATE OR REPLACE VIEW v_device_current_status AS
SELECT 
    d.id as device_id,
    d.device_code,
    d.device_name,
    p.name as project_name,
    latest.timestamp as last_reading,
    latest.accumulated_value,
    latest.delta_value,
    latest.classification,
    CASE 
        WHEN latest.timestamp < NOW() - INTERVAL '30 minutes' THEN 'offline'
        WHEN latest.classification = 'quarantine' THEN 'critical'
        WHEN latest.classification = 'uncertain' THEN 'warning'
        ELSE 'normal'
    END as status
FROM devices d
JOIN projects p ON d.project_id = p.id
LEFT JOIN LATERAL (
    SELECT 
        timestamp, 
        accumulated_value, 
        delta_value, 
        classification::text
    FROM raw_records
    WHERE device_id = d.id
    ORDER BY timestamp DESC
    LIMIT 1
) latest ON true
WHERE d.status = 'active';

-- Comentario sobre la vista
COMMENT ON VIEW v_device_current_status IS 'Estado actual de todos los dispositivos activos';

-- Vista para análisis de calidad de datos
CREATE OR REPLACE VIEW v_data_quality_summary AS
WITH recent_records AS (
    SELECT 
        device_id,
        classification,
        COUNT(*) as count
    FROM raw_records
    WHERE timestamp >= CURRENT_DATE - INTERVAL '24 hours'
    GROUP BY device_id, classification
),
device_totals AS (
    SELECT 
        device_id,
        SUM(count) as total_count
    FROM recent_records
    GROUP BY device_id
)
SELECT 
    d.device_code,
    COALESCE(valid_counts.count, 0)::INTEGER as valid_count,
    COALESCE(uncertain_counts.count, 0)::INTEGER as uncertain_count,
    COALESCE(quarantine_counts.count, 0)::INTEGER as quarantine_count,
    COALESCE(dt.total_count, 0)::INTEGER as total_count,
    CASE 
        WHEN COALESCE(dt.total_count, 0) > 0 
        THEN ROUND(100.0 * COALESCE(valid_counts.count, 0) / dt.total_count, 2)
        ELSE 0
    END as validity_percentage
FROM devices d
LEFT JOIN device_totals dt ON d.id = dt.device_id
LEFT JOIN recent_records valid_counts 
    ON d.id = valid_counts.device_id AND valid_counts.classification = 'valid'
LEFT JOIN recent_records uncertain_counts 
    ON d.id = uncertain_counts.device_id AND uncertain_counts.classification = 'uncertain'
LEFT JOIN recent_records quarantine_counts 
    ON d.id = quarantine_counts.device_id AND quarantine_counts.classification = 'quarantine'
WHERE d.status = 'active'
ORDER BY d.device_code;

-- Comentario sobre la vista
COMMENT ON VIEW v_data_quality_summary IS 'Resumen de calidad de datos de las últimas 24 horas';

-- Vista para análisis de alertas por dispositivo
CREATE OR REPLACE VIEW v_alerts_summary AS
SELECT 
    d.device_code,
    d.device_name,
    COUNT(*) FILTER (WHERE a.resolved = FALSE) as active_alerts,
    COUNT(*) FILTER (WHERE a.alert_type = 'negative_delta') as negative_delta_count,
    COUNT(*) FILTER (WHERE a.alert_type = 'frozen_value') as frozen_value_count,
    COUNT(*) FILTER (WHERE a.alert_type = 'consecutive_quarantine') as quarantine_count,
    MAX(a.created_at) as last_alert_time
FROM devices d
LEFT JOIN alerts a ON d.id = a.device_id
WHERE a.created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY d.id, d.device_code, d.device_name
HAVING COUNT(*) > 0
ORDER BY active_alerts DESC, last_alert_time DESC;

-- Comentario sobre la vista
COMMENT ON VIEW v_alerts_summary IS 'Resumen de alertas por dispositivo de los últimos 7 días';

-- Vista para tendencia de generación diaria
CREATE OR REPLACE VIEW v_daily_generation AS
SELECT 
    d.device_code,
    DATE(vr.timestamp) as generation_date,
    MAX(vr.accumulated_value) - MIN(vr.accumulated_value) as daily_generation,
    COUNT(*) as reading_count,
    AVG(vr.delta_value) as avg_delta
FROM devices d
JOIN valid_records vr ON d.id = vr.device_id
WHERE vr.timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY d.id, d.device_code, DATE(vr.timestamp)
ORDER BY d.device_code, generation_date DESC;

-- Comentario sobre la vista
COMMENT ON VIEW v_daily_generation IS 'Generación diaria por dispositivo de los últimos 30 días';

-- Función para refrescar la vista materializada
CREATE OR REPLACE FUNCTION refresh_hourly_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_device_hourly_stats;
    RAISE NOTICE 'Vista materializada mv_device_hourly_stats actualizada exitosamente';
END;
$$ LANGUAGE plpgsql;

-- Comentario sobre la función
COMMENT ON FUNCTION refresh_hourly_stats() IS 'Actualiza la vista materializada de estadísticas horarias';

-- Crear un job programado para actualizar la vista materializada (requiere pg_cron extension)
-- Si pg_cron está disponible, descomentar las siguientes líneas:
/*
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule(
    'refresh-hourly-stats',
    '0 * * * *', -- Cada hora
    $$SELECT erco_monitor.refresh_hourly_stats();$$
);
*/