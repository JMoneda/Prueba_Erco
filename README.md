# ERCO Energy Monitor 🌟

Sistema de monitoreo en tiempo real para plataformas de energía solar fotovoltaica, con validación automática de datos, detección de anomalías y alertas inteligentes.

## 📋 Características Principales

- **Ingesta de Datos en Tiempo Real**: Procesamiento de datos cada 15 minutos de múltiples inversores
- **validación Inteligente**: Clasificación automática en válido, incierto o cuarentena
- **Sistema de Alertas**: Notificaciones en tiempo real vía WebSocket para condiciones críticas
- **Dashboard Interactivo**: Visualización de métricas y estado de dispositivos
- **Análisis Histórico**: Estadísticas basadas en comportamiento de los últimos 7 días
- **Simulador Integrado**: Generación de datos realistas con errores intencionales para pruebas

## 🏗️ Arquitectura

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL │
│   (Nginx)   │◀────│  (FastAPI)  │◀────│     (DB)    │
└─────────────┘     └─────────────┘     └─────────────┘
│                    │
└────WebSocket───────┘

### Stack Tecnológico

- **Backend**: Python 3.11, FastAPI, SQLAlchemy
- **Base de Datos**: PostgreSQL 15 con vistas materializadas
- **Frontend**: HTML5, CSS3, JavaScript vanilla, Chart.js
- **Infraestructura**: Docker, Docker Compose, Nginx
- **Comunicación Real-time**: WebSockets

## 🚀 Instalación y Ejecución

### Prerrequisitos

- Docker Desktop (incluye Docker y Docker Compose)
- Git
- 4GB RAM mínimo disponible
- Puertos 80, 8000 y 5432 disponibles

### Pasos de Instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/tu-usuario/erco-energy-monitor.git
cd erco-energy-monitor

### Configurar variables de entorno (opcional)

# Crear archivo .env en la raíz del proyecto
cp .env.example .env
# Editar según necesidades

### Iniciar servicios con Docker Compose

# Construir e iniciar todos los servicios
docker-compose up -d --build

# Verificar que todos los servicios estén corriendo
docker-compose ps

### Acceder a la aplicación


Frontend: http://localhost
API Documentation: http://localhost:8000/docs
PostgreSQL: localhost:5432 (usuario: postgres, contraseña: postgres)