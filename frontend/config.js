// frontend/config.js
// Configuración del frontend - Centralizada y adaptable por entorno

window.APP_CONFIG = {
    // URLs dinámicas según entorno
    API_URL: window.location.hostname === 'localhost' 
        ? 'http://localhost:8000' 
        : `${window.location.protocol}//${window.location.hostname}:8000`,
    
    WS_URL: window.location.hostname === 'localhost'
        ? 'ws://localhost:8000/ws/alerts'
        : `ws://${window.location.hostname}:8000/ws/alerts`,
    
    // Configuración de la aplicación
    APP_NAME: 'ERCO Energy Monitor',
    REFRESH_INTERVAL: 15000, // 15 segundos
    DEBUG: window.location.hostname === 'localhost',
    
    // Configuración adicional
    PING_INTERVAL: 30000, // 30 segundos
    CHART_COLORS: {
        valid: '#10b981',
        uncertain: '#f59e0b', 
        quarantine: '#ef4444'
    },
    
    // Límites y configuración UI
    MAX_RECENT_RECORDS: 20,
    MAX_ALERTS_DISPLAY: 10
};

// Log de configuración en modo debug
if (window.APP_CONFIG.DEBUG) {
    console.log('🔧 APP_CONFIG cargada:', window.APP_CONFIG);
}