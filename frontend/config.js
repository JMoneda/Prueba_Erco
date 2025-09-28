// Configuración del frontend
// Estas variables se pueden sobrescribir en producción

window.APP_CONFIG = {
    API_URL: window.API_URL || 'http://localhost:8000',
    WS_URL: window.WS_URL || 'ws://localhost:8000/ws/alerts',
    APP_NAME: 'ERCO Energy Monitor',
    REFRESH_INTERVAL: 15000, // 15 segundos
    DEBUG: false
};