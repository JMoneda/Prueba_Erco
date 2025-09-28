#!/bin/bash

echo "🚀 Configuración inicial de ERCO Energy Monitor"
echo "=============================================="

# Verificar si existe .env
if [ ! -f .env ]; then
    echo "📝 Creando archivo .env desde .env.example..."
    cp .env.example .env
    
    echo "⚠️  Por favor, edita el archivo .env con tus credenciales:"
    echo "   - DB_PASSWORD: Configura una contraseña segura"
    echo "   - SECRET_KEY: Genera una con 'python scripts/generate_secret.py'"
    echo ""
    read -p "Presiona Enter cuando hayas configurado .env..."
else
    echo "✅ Archivo .env encontrado"
fi

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado. Por favor, instálalo primero."
    exit 1
fi

echo "✅ Docker está instalado"

# Verificar Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado. Por favor, instálalo primero."
    exit 1
fi

echo "✅ Docker Compose está instalado"

# Construir contenedores
echo "🔨 Construyendo contenedores..."
docker-compose build

# Iniciar servicios
echo "🚀 Iniciando servicios..."
docker-compose up -d

# Esperar a que la base de datos esté lista
echo "⏳ Esperando a que PostgreSQL esté listo..."
sleep 10

# Verificar estado
echo "📊 Verificando estado de los servicios..."
docker-compose ps

echo ""
echo "✅ Configuración completada!"
echo ""
echo "🌐 Accede a la aplicación en:"
echo "   - Frontend: http://localhost"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo ""
echo "📝 Para ver los logs:"
echo "   docker-compose logs -f"