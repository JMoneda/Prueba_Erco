/**
 * ERCO Energy Monitor - Cliente Frontend
 * Maneja la interfaz de usuario y comunicación en tiempo real
 */

class ERCOMonitor {
    constructor() {
        this.apiUrl = 'http://localhost:8000';
        this.wsUrl = 'ws://localhost:8000/ws/alerts';
        this.ws = null;
        this.devices = [];
        this.alerts = [];
        this.qualityChart = null;
        
        this.init();
    }

    async init() {
        console.log('Inicializando ERCO Energy Monitor...');
        
        // Conectar WebSocket para alertas en tiempo real
        this.connectWebSocket();
        
        // Cargar datos iniciales
        await this.loadDevices();
        await this.loadAlerts();
        await this.loadQualityStats();
        
        // Configurar actualización periódica
        setInterval(() => this.updateDashboard(), 15000); // Cada 15 segundos
        
        // Configurar event listeners
        this.setupEventListeners();
    }

    connectWebSocket() {
        // Establecer conexión WebSocket para alertas en tiempo real
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket conectado');
            this.updateConnectionStatus(true);
            
            // Enviar ping cada 30 segundos para mantener conexión
            setInterval(() => {
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);
        };
        
        this.ws.onmessage = (event) => {
            const data = event.data;
            
            // CORRECCIÓN: Verificar si es 'pong' antes de parsear JSON
            if (data === 'pong') {
                console.log('Pong recibido');
                return;
            }
            
            try {
                // Es una alerta
                const alert = JSON.parse(data);
                console.log('Nueva alerta recibida:', alert);
                this.handleNewAlert(alert);
            } catch (e) {
                console.error('Error parseando mensaje WebSocket:', e, data);
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket desconectado');
            this.updateConnectionStatus(false);
            
            // Reconectar después de 5 segundos
            setTimeout(() => this.connectWebSocket(), 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('Error WebSocket:', error);
        };
    }

    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');
        
        if (connected) {
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'Conectado';
        } else {
            statusDot.className = 'status-dot disconnected';
            statusText.textContent = 'Desconectado';
        }
    }

    async loadDevices() {
        try {
            const response = await fetch(`${this.apiUrl}/api/devices`);
            this.devices = await response.json();
            
            // Actualizar selector de dispositivos
            this.updateDeviceFilter();
            
            // Cargar estado de cada dispositivo
            await this.updateDevicesStatus();
            
        } catch (error) {
            console.error('Error cargando dispositivos:', error);
        }
    }

    async updateDevicesStatus() {
        const devicesGrid = document.getElementById('devices-grid');
        devicesGrid.innerHTML = '';
        
        // CORRECCIÓN: Solo procesar dispositivos activos que existen
        for (const device of this.devices) {
            try {
                const response = await fetch(`${this.apiUrl}/api/devices/${device.id}/status`);
                
                if (response.ok) {
                    const status = await response.json();
                    // Crear tarjeta de dispositivo
                    const card = this.createDeviceCard(status);
                    devicesGrid.appendChild(card);
                } else if (response.status === 404) {
                    // Dispositivo no tiene estado aún (sin registros)
                    const card = this.createDeviceCard({
                        device_id: device.id,
                        device_code: device.device_code,
                        device_name: device.device_name,
                        project_name: device.project_name,
                        status: 'offline',
                        accumulated_value: null,
                        delta_value: null,
                        classification: null
                    });
                    devicesGrid.appendChild(card);
                }
            } catch (error) {
                console.error(`Error obteniendo estado del dispositivo ${device.id}:`, error);
            }
        }
    }

    createDeviceCard(status) {
        const card = document.createElement('div');
        // CORRECCIÓN: Verificar que status existe antes de usar toUpperCase
        const deviceStatus = status.status || 'unknown';
        card.className = `device-card ${deviceStatus.toLowerCase()}`;
        
        const lastValue = status.accumulated_value ? status.accumulated_value.toFixed(2) : 'N/A';
        const deltaValue = status.delta_value ? `Δ ${status.delta_value.toFixed(2)}` : '';
        
        card.innerHTML = `
            <div class="device-code">${status.device_code}</div>
            <div class="device-status">${deviceStatus.toUpperCase()}</div>
            <div class="device-value">${lastValue} kWh</div>
            <div class="device-status">${deltaValue}</div>
        `;
        
        return card;
    }

    async loadAlerts() {
        try {
            const response = await fetch(`${this.apiUrl}/api/alerts?resolved=false`);
            this.alerts = await response.json();
            
            this.updateAlertsDisplay();
            
        } catch (error) {
            console.error('Error cargando alertas:', error);
        }
    }

    updateAlertsDisplay() {
        const container = document.getElementById('alerts-container');
        
        if (this.alerts.length === 0) {
            container.innerHTML = '<p class="no-alerts">No hay alertas activas</p>';
            return;
        }
        
        container.innerHTML = '';
        
        // Mostrar últimas 10 alertas
        this.alerts.slice(0, 10).forEach(alert => {
            const alertElement = this.createAlertElement(alert);
            container.appendChild(alertElement);
        });
    }

    createAlertElement(alert) {
        const div = document.createElement('div');
        div.className = `alert-item ${alert.severity}`;
        
        const time = new Date(alert.created_at).toLocaleTimeString();
        
        div.innerHTML = `
            <div class="alert-header">
                <span class="alert-title">${alert.device_code} - ${this.getAlertTypeLabel(alert.alert_type)}</span>
                <span class="alert-time">${time}</span>
            </div>
            <div class="alert-message">${alert.message}</div>
        `;
        
        // Click para resolver alerta
        div.addEventListener('click', () => this.resolveAlert(alert.id));
        
        return div;
    }

    getAlertTypeLabel(type) {
        const labels = {
            'consecutive_quarantine': 'Cuarentena Consecutiva',
            'negative_delta': 'Delta Negativo',
            'frozen_value': 'Valor Congelado'
        };
        return labels[type] || type;
    }

    handleNewAlert(alert) {
        // Añadir al inicio del array
        this.alerts.unshift(alert);
        
        // Actualizar display
        this.updateAlertsDisplay();
        
        // Mostrar notificación del navegador si está permitido
        if (Notification.permission === 'granted') {
            new Notification('ERCO Energy Monitor', {
                body: alert.message,
                icon: '⚡'
            });
        }
        
        // Reproducir sonido de alerta
        this.playAlertSound();
    }

    playAlertSound() {
        // Crear sonido simple con Web Audio API
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (e) {
            console.log('No se pudo reproducir sonido:', e);
        }
    }

    async resolveAlert(alertId) {
        try {
            const response = await fetch(`${this.apiUrl}/api/alerts/${alertId}/resolve`, {
                method: 'PUT'
            });
            
            if (response.ok) {
                // Remover de la lista
                this.alerts = this.alerts.filter(a => a.id !== alertId);
                this.updateAlertsDisplay();
            }
            
        } catch (error) {
            console.error('Error resolviendo alerta:', error);
        }
    }

    async loadQualityStats() {
        try {
            const response = await fetch(`${this.apiUrl}/api/statistics/quality`);
            const stats = await response.json();
            
            this.updateQualityChart(stats);
            this.updateStatsSummary(stats);
            
        } catch (error) {
            console.error('Error cargando estadísticas:', error);
        }
    }

    updateQualityChart(stats) {
        const ctx = document.getElementById('quality-chart').getContext('2d');
        
        // CORRECCIÓN: Destruir chart anterior si existe
        if (this.qualityChart) {
            this.qualityChart.destroy();
            this.qualityChart = null;
        }
        
        // Preparar datos
        const labels = stats.map(s => s.device_code);
        const validData = stats.map(s => s.valid_count);
        const uncertainData = stats.map(s => s.uncertain_count);
        const quarantineData = stats.map(s => s.quarantine_count);
        
        // Crear chart con configuración correcta
        this.qualityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Válidos',
                        data: validData,
                        backgroundColor: '#10b981'
                    },
                    {
                        label: 'Inciertos',
                        data: uncertainData,
                        backgroundColor: '#f59e0b'
                    },
                    {
                        label: 'Cuarentena',
                        data: quarantineData,
                        backgroundColor: '#ef4444'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true, // CORRECCIÓN: Mantener proporción
                aspectRatio: 2, // CORRECCIÓN: Proporción fija
                scales: {
                    x: {
                        stacked: true
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    updateStatsSummary(stats) {
        const container = document.getElementById('stats-summary');
        
        // Calcular totales
        const totals = stats.reduce((acc, s) => {
            acc.valid += s.valid_count;
            acc.uncertain += s.uncertain_count;
            acc.quarantine += s.quarantine_count;
            acc.total += s.total_count;
            return acc;
        }, { valid: 0, uncertain: 0, quarantine: 0, total: 0 });
        
        const validityPercentage = totals.total > 0 
            ? (totals.valid / totals.total * 100).toFixed(1) 
            : 0;
        
        container.innerHTML = `
            <div class="stat-item">
                <div class="stat-label">Total Válidos</div>
                <div class="stat-value" style="color: #10b981">${totals.valid}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Total Inciertos</div>
                <div class="stat-value" style="color: #f59e0b">${totals.uncertain}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">% validez</div>
                <div class="stat-value">${validityPercentage}%</div>
            </div>
        `;
    }

    async loadRecords() {
        const deviceFilter = document.getElementById('device-filter').value;
        const classificationFilter = document.getElementById('classification-filter').value;
        
        // Construir URL con filtros
        let url = `${this.apiUrl}/api/devices/`;
        if (deviceFilter) {
            url += `${deviceFilter}/records?hours=24`;
            if (classificationFilter) {
                url += `&classification=${classificationFilter}`;
            }
        } else {
            // Si no hay dispositivo seleccionado, mostrar mensaje
            document.getElementById('records-tbody').innerHTML = 
                '<tr><td colspan="5" style="text-align: center">Seleccione un dispositivo</td></tr>';
            return;
        }
        
        try {
            const response = await fetch(url);
            if (response.ok) {
                const records = await response.json();
                this.updateRecordsTable(records, deviceFilter);
            } else {
                console.error('Error obteniendo registros:', response.status);
                document.getElementById('records-tbody').innerHTML = 
                    '<tr><td colspan="5" style="text-align: center; color: red">Error cargando registros</td></tr>';
            }
        } catch (error) {
            console.error('Error cargando registros:', error);
        }
    }

    updateRecordsTable(records, deviceId) {
        const tbody = document.getElementById('records-tbody');
        tbody.innerHTML = '';
        
        // Obtener nombre del dispositivo
        const device = this.devices.find(d => d.id == deviceId);
        const deviceName = device ? device.device_code : 'Desconocido';
        
        // CORRECCIÓN: Verificar que records es un array
        if (!Array.isArray(records)) {
            console.error('Records no es un array:', records);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: red">Error: datos inválidos</td></tr>';
            return;
        }
        
        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center">No hay registros</td></tr>';
            return;
        }
        
        // Mostrar últimos 20 registros
        records.slice(0, 20).forEach(record => {
            const row = document.createElement('tr');
            
            const timestamp = new Date(record.timestamp).toLocaleString();
            const value = record.accumulated_value !== null ? record.accumulated_value.toFixed(2) : 'N/A';
            const delta = record.delta_value !== null ? record.delta_value.toFixed(2) : 'N/A';
            
            row.innerHTML = `
                <td>${deviceName}</td>
                <td>${timestamp}</td>
                <td>${value}</td>
                <td>${delta}</td>
                <td>
                    <span class="classification-badge ${record.classification || ''}">
                        ${record.classification || 'N/A'}
                    </span>
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }

    updateDeviceFilter() {
        const select = document.getElementById('device-filter');
        
        // Mantener selección actual
        const currentValue = select.value;
        
        select.innerHTML = '<option value="">Todos los dispositivos</option>';
        
        this.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.id;
            option.textContent = `${device.device_code} - ${device.device_name}`;
            select.appendChild(option);
        });
        
        // Restaurar selección
        select.value = currentValue;
    }

    setupEventListeners() {
        // Filtros de registros
        document.getElementById('device-filter').addEventListener('change', () => {
            this.loadRecords();
        });
        
        document.getElementById('classification-filter').addEventListener('change', () => {
            this.loadRecords();
        });
        
        // Solicitar permisos de notificación
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    async updateDashboard() {
        // Actualizar componentes del dashboard
        await this.updateDevicesStatus();
        await this.loadQualityStats();
        
        // Actualizar registros si hay un dispositivo seleccionado
        if (document.getElementById('device-filter').value) {
            await this.loadRecords();
        }
    }
}

// Inicializar aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.ercoMonitor = new ERCOMonitor();
});