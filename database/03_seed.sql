-- Script de datos iniciales para ERCO Energy Monitor
-- Compatible con PostgreSQL 17

SET search_path TO erco_monitor;

-- Limpiar datos existentes (opcional, comentar en producción)
TRUNCATE TABLE alerts, raw_records, valid_records, device_statistics, devices, projects RESTART IDENTITY CASCADE;

-- Insertar proyectos de prueba
INSERT INTO projects (name, location, installed_capacity) VALUES
    ('Planta Solar Norte', 'Antioquia, Colombia', 500.00),
    ('Planta Solar Sur', 'Valle del Cauca, Colombia', 750.00),
    ('Planta Solar Este', 'Cundinamarca, Colombia', 300.00);

-- Insertar dispositivos para Planta Norte
INSERT INTO devices (project_id, device_code, device_name, nominal_power, status) 
SELECT 
    1,
    'INV-N-' || LPAD(generate_series::text, 3, '0'),
    'Inversor Norte ' || generate_series,
    50.00,
    'active'
FROM generate_series(1, 5);

-- Insertar dispositivos para Planta Sur
INSERT INTO devices (project_id, device_code, device_name, nominal_power, status) 
SELECT 
    2,
    'INV-S-' || LPAD(generate_series::text, 3, '0'),
    'Inversor Sur ' || generate_series,
    75.00,
    'active'
FROM generate_series(1, 5);

-- Insertar dispositivos para Planta Este (algunos inactivos para pruebas)
INSERT INTO devices (project_id, device_code, device_name, nominal_power, status) 
SELECT 
    3,
    'INV-E-' || LPAD(generate_series::text, 3, '0'),
    'Inversor Este ' || generate_series,
    30.00,
    CASE WHEN generate_series <= 3 THEN 'active' ELSE 'maintenance' END
FROM generate_series(1, 5);

-- Generar registros históricos de prueba
DO $$
DECLARE
    device RECORD;
    current_ts TIMESTAMP;
    accumulated_value DECIMAL(15,3);
    delta_value DECIMAL(10,3);
    hour_of_day INTEGER;
    base_generation DECIMAL(10,3);
    weather_factor DECIMAL(5,3);
    device_efficiency DECIMAL(5,3);
    error_probability DECIMAL(3,2);
    classification_type data_classification;
    validation_msg TEXT;
BEGIN
    -- Para cada dispositivo activo
    FOR device IN 
        SELECT id, nominal_power 
        FROM devices 
        WHERE status = 'active' 
        ORDER BY id
    LOOP
        -- Inicializar valor acumulado base aleatorio
        accumulated_value := 1000.0 + (random() * 4000);
        
        -- Eficiencia específica del dispositivo
        device_efficiency := 0.85 + (random() * 0.13); -- Entre 85% y 98%
        
        -- Comenzar hace 7 días
        current_ts := DATE_TRUNC('hour', NOW() - INTERVAL '7 days');
        
        -- Generar datos para los últimos 7 días
        WHILE current_ts < NOW() LOOP
            hour_of_day := EXTRACT(hour FROM current_ts);
            
            -- Solo generar durante horas de sol (6am - 6pm)
            IF hour_of_day >= 6 AND hour_of_day <= 18 THEN
                -- Calcular generación base usando perfil solar
                IF hour_of_day >= 6 AND hour_of_day <= 18 THEN
                    base_generation := sin(pi() * (hour_of_day - 6.0) / 12.0);
                ELSE
                    base_generation := 0;
                END IF;
                
                -- Factor climático aleatorio (nubes, lluvia, etc.)
                weather_factor := 0.7 + (random() * 0.3);
                
                -- Calcular delta (generación en 15 minutos)
                delta_value := device.nominal_power * base_generation * weather_factor * device_efficiency * 0.25;
                
                -- Probabilidad de error (5% para datos históricos)
                error_probability := random();
                
                -- Introducir algunos errores para hacer los datos más realistas
                IF error_probability < 0.02 THEN
                    -- 2% de probabilidad de delta negativo
                    delta_value := -1 * (random() * 10 + 5);
                    classification_type := 'quarantine';
                    validation_msg := 'Delta negativo detectado - posible falla del inversor';
                ELSIF error_probability < 0.04 THEN
                    -- 2% de probabilidad de valor congelado
                    delta_value := 0;
                    IF hour_of_day >= 8 AND hour_of_day <= 16 THEN
                        classification_type := 'quarantine';
                        validation_msg := 'Valor congelado durante período de generación';
                    ELSE
                        classification_type := 'valid';
                        validation_msg := 'Sin generación - horario de baja radiación';
                    END IF;
                ELSIF error_probability < 0.05 THEN
                    -- 1% de probabilidad de salto atípico
                    delta_value := delta_value * (2.5 + random());
                    classification_type := 'uncertain';
                    validation_msg := 'Salto atípico detectado - requiere verificación';
                ELSE
                    -- 95% de datos válidos
                    classification_type := 'valid';
                    validation_msg := 'Dentro de rangos históricos normales';
                END IF;
                
                -- Actualizar valor acumulado
                accumulated_value := GREATEST(0, accumulated_value + delta_value);
                
                -- Insertar en raw_records
                INSERT INTO raw_records (
                    device_id, 
                    timestamp, 
                    accumulated_value, 
                    delta_value, 
                    classification, 
                    validation_reason,
                    created_at
                ) VALUES (
                    device.id,
                    current_ts,
                    accumulated_value,
                    delta_value,
                    classification_type,
                    validation_msg,
                    current_ts
                );
                
                -- Si es válido, también insertar en valid_records
                IF classification_type = 'valid' THEN
                    INSERT INTO valid_records (
                        device_id,
                        timestamp,
                        accumulated_value,
                        delta_value,
                        created_at
                    ) VALUES (
                        device.id,
                        current_ts,
                        accumulated_value,
                        delta_value,
                        current_ts
                    );
                END IF;
            END IF;
            
            -- Avanzar 15 minutos
            current_ts := current_ts + INTERVAL '15 minutes';
        END LOOP;
        
        RAISE NOTICE 'Datos generados para dispositivo %', device.id;
    END LOOP;
END $$;

-- Generar algunas alertas de ejemplo
INSERT INTO alerts (device_id, alert_type, severity, message, details, resolved, created_at)
SELECT 
    d.id,
    'consecutive_quarantine',
    'critical',
    'Dispositivo ' || d.device_code || ': 3 registros consecutivos en cuarentena',
    jsonb_build_object(
        'consecutive_count', 3,
        'device_code', d.device_code,
        'timestamp', NOW()
    ),
    FALSE,
    NOW() - INTERVAL '2 hours'
FROM devices d
WHERE d.id IN (1, 3, 5)
LIMIT 3;

-- Actualizar vista materializada con los datos generados
REFRESH MATERIALIZED VIEW mv_device_hourly_stats;

-- Mostrar resumen de datos generados
DO $$
DECLARE
    total_records INTEGER;
    valid_records_count INTEGER;
    uncertain_records INTEGER;
    quarantine_records INTEGER;
    active_devices INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_records FROM raw_records;
    SELECT COUNT(*) INTO valid_records_count FROM raw_records WHERE classification = 'valid';
    SELECT COUNT(*) INTO uncertain_records FROM raw_records WHERE classification = 'uncertain';
    SELECT COUNT(*) INTO quarantine_records FROM raw_records WHERE classification = 'quarantine';
    SELECT COUNT(*) INTO active_devices FROM devices WHERE status = 'active';
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RESUMEN DE DATOS GENERADOS';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Dispositivos activos: %', active_devices;
    RAISE NOTICE 'Total de registros: %', total_records;
    RAISE NOTICE 'Registros válidos: % (%.1f%%)', valid_records_count, (valid_records_count::float / total_records * 100);
    RAISE NOTICE 'Registros inciertos: % (%.1f%%)', uncertain_records, (uncertain_records::float / total_records * 100);
    RAISE NOTICE 'Registros en cuarentena: % (%.1f%%)', quarantine_records, (quarantine_records::float / total_records * 100);
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Base de datos inicializada exitosamente';
    RAISE NOTICE '========================================';
END $$;