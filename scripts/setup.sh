#!/bin/bash
set -e  # Salir si hay errores

echo "🚀 ERCO Energy Monitor - Instalación Automática"
echo "================================================"

# Verificar prerrequisitos
echo "🔍 Verificando prerrequisitos..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado."
    echo "   Instalar desde: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado."
    echo "   Instalar desde: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker y Docker Compose encontrados"

# Configurar .env
if [ ! -f .env ]; then
    echo "📝 Creando archivo .env..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANTE: Configura las siguientes variables en .env:"
    echo "   - DB_PASSWORD (contraseña segura para PostgreSQL)"
    echo "   - SECRET_KEY (ejecuta: python scripts/generate_secret.py)"
    echo ""
    read -p "Presiona Enter cuando hayas configurado .env..."
else
    echo "✅ Archivo .env encontrado"
fi

# Verificar puertos
echo "🔍 Verificando puertos disponibles..."
if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Puerto 80 en uso. El frontend podría no iniciarse correctamente."
fi

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Puerto 8000 en uso. El backend podría no iniciarse correctamente."
fi

# Construir e iniciar
echo "🔨 Construyendo aplicación..."
docker-compose build --no-cache

echo "🚀 Iniciando servicios..."
docker-compose up -d

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL inicialice..."
sleep 15

# Verificar estado
echo "📊 Estado de los servicios:"
docker-compose ps

# Verificar salud
echo "🏥 Verificando salud del sistema..."
sleep 5

if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "✅ Backend funcionando correctamente"
else
    echo "⚠️  Backend podría tener problemas. Verificar logs:"
    echo "   docker-compose logs backend"
fi

echo ""
echo "🎉 ¡Instalación completada!"
echo ""
echo "📊 Acceder a la aplicación:"
echo "   🌐 Dashboard: http://localhost"
echo "   📡 API Docs:  http://localhost:8000/docs"
echo "   💾 PostgreSQL: localhost:5432"
echo ""
echo "📝 Comandos útiles:"
echo "   Ver logs:     docker-compose logs -f"
echo "   Detener:      docker-compose down"
echo "   Reiniciar:    docker-compose restart"