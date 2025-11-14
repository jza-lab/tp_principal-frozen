document.addEventListener('DOMContentLoaded', () => {
    // Estado de la aplicación
    let selectedPedidos = new Set();
    let vehiculo = null;
    let viewMode = 'map'; // 'map' o 'list'
    let sortedRoute = [];

    // Referencias al DOM
    const mapContainer = document.getElementById('map-container');
    const mapView = document.getElementById('map-view');
    const listView = document.getElementById('list-view');
    const viewMapBtn = document.getElementById('view-map-btn');
    const viewListBtn = document.getElementById('view-list-btn');
    const disponiblesGrid = document.getElementById('disponibles-grid');
    const listaOptimizadaContainer = document.getElementById('lista-pedidos-optimizada');
    
    // Panel derecho
    const patenteInput = document.getElementById('patente-input');
    const buscarVehiculoBtn = document.getElementById('buscar-vehiculo-btn');
    const vehiculoInfo = document.getElementById('vehiculo-info');
    const vehiculoPatente = document.getElementById('vehiculo-patente');
    const vehiculoConductor = document.getElementById('vehiculo-conductor');
    const vehiculoDni = document.getElementById('vehiculo-dni');
    const vehiculoCapacidad = document.getElementById('vehiculo-capacidad');
    const selectedCount = document.getElementById('selected-count');
    const totalWeight = document.getElementById('total-weight');
    const totalDistance = document.getElementById('total-distance');
    const totalTime = document.getElementById('total-time');
    const capacidadContainer = document.getElementById('capacidad-container');
    const capacidadPorcentaje = document.getElementById('capacidad-porcentaje');
    const capacidadBar = document.getElementById('capacidad-bar');
    const capacidadAlerta = document.getElementById('capacidad-alerta');
    const observacionesInput = document.getElementById('observaciones-input');
    const confirmarDespachoBtn = document.getElementById('confirmar-despacho-btn');
    const ayudaDespacho = document.getElementById('ayuda-despacho');

    // Mapa Leaflet
    let mapInstance = null;
    const markers = [];
    let routePolyline = null;
    const DEPOSITO_COORDS = [-34.603722, -58.381592];

    // --- INICIALIZACIÓN ---

    const initMap = () => {
        if (!mapContainer || mapInstance) return;

        mapInstance = L.map(mapContainer).setView(DEPOSITO_COORDS, 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(mapInstance);

        // Marcador del depósito
        L.marker(DEPOSITO_COORDS, {
            icon: L.divIcon({
                className: 'custom-depot-marker',
                html: '🏭',
                iconSize: [40, 40]
            })
        }).addTo(mapInstance).bindPopup('Depósito Central');
    };

    // --- LÓGICA DE RENDERIZADO ---

    const render = () => {
        updateMapView();
        updateListView();
        updateInfoPanel();
    };

    const updateMapView = () => {
        if (!mapInstance) return;

        // Limpiar marcadores y ruta
        markers.forEach(m => m.remove());
        markers.length = 0;
        if (routePolyline) {
            routePolyline.remove();
            routePolyline = null;
        }

        // Crear marcadores para cada pedido
        pedidosSimulados.forEach((pedido) => {
            const isSelected = selectedPedidos.has(pedido.id);
            const orderIndex = sortedRoute.findIndex(p => p.id === pedido.id);
            const orderNumber = orderIndex !== -1 ? orderIndex + 1 : 0;

            const markerHtml = `
                <div class="marker-wrapper ${isSelected ? 'selected' : ''}">
                    ${isSelected && orderNumber > 0 ? `<div class="marker-order-number">${orderNumber}</div>` : ''}
                    <div class="marker-content">📦 #${pedido.id}</div>
                </div>`;
            
            const marker = L.marker([pedido.direccion.latitud, pedido.direccion.longitud], {
                icon: L.divIcon({
                    className: 'custom-marker-icon',
                    html: markerHtml,
                })
            }).addTo(mapInstance);

            marker.on('click', () => handlePedidoSelection(pedido.id));
            marker.bindPopup(`
                <b>Pedido #${pedido.id}</b><br>
                ${pedido.cliente.nombre}<br>
                ${pedido.direccion.calle} ${pedido.direccion.altura}<br>
                📦 ${pedido.peso_total_calculado_kg} kg | 📍 ${pedido.distancia_km} km | 🕐 ~${pedido.tiempo_estimado}`);
            
            markers.push(marker);
        });

        // Dibujar ruta si hay pedidos seleccionados
        if (sortedRoute.length > 0) {
            const routeCoords = [
                DEPOSITO_COORDS,
                ...sortedRoute.map(p => [p.direccion.latitud, p.direccion.longitud]),
                DEPOSITO_COORDS
            ];

            routePolyline = L.polyline(routeCoords, {
                color: '#0d6efd',
                weight: 3,
                opacity: 0.8,
                dashArray: '8, 8'
            }).addTo(mapInstance);
            
            markers.push(routePolyline);
            mapInstance.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });
        }
    };
    
    const updateListView = () => {
        // Sincronizar el estado de los checkboxes en la tabla con el estado de la aplicación
        document.querySelectorAll('#list-view .pedido-checkbox').forEach(checkbox => {
            const pedidoId = parseInt(checkbox.value, 10);
            const row = checkbox.closest('tr');
            if (row) { // Asegurarse de que la fila exista
                if (selectedPedidos.has(pedidoId)) {
                    checkbox.checked = true;
                    row.classList.add('table-primary'); // Clase de Bootstrap para resaltar
                } else {
                    checkbox.checked = false;
                    row.classList.remove('table-primary');
                }
            }
        });

        // Renderizar lista de ruta optimizada
        if (sortedRoute.length > 0) {
            const rutaHtml = `
                <h4>Ruta Optimizada (${sortedRoute.length} paradas)</h4>
                <div class="ruta-timeline">
                    <div class="ruta-item inicio">
                        <div class="ruta-icono">🏭</div>
                        <div class="ruta-info">
                            <strong>INICIO - Depósito Central</strong>
                            <span>Punto de partida</span>
                        </div>
                    </div>
                    ${sortedRoute.map((pedido, index) => `
                        <div class="ruta-flecha">↓</div>
                        <div class="ruta-item">
                            <div class="ruta-orden">${index + 1}</div>
                            <div class="ruta-info">
                                <strong>PED-${pedido.id} - ${pedido.cliente.nombre}</strong>
                                <span>${pedido.direccion.calle} ${pedido.direccion.altura}</span>
                            </div>
                        </div>
                    `).join('')}
                    <div class="ruta-flecha">↓</div>
                     <div class="ruta-item fin">
                        <div class="ruta-icono">🏁</div>
                        <div class="ruta-info">
                            <strong>FIN - Retorno al Depósito</strong>
                            <span>Ruta completada</span>
                        </div>
                    </div>
                </div>`;
            listaOptimizadaContainer.innerHTML = rutaHtml;
        } else {
            listaOptimizadaContainer.innerHTML = '';
        }
    };

    const updateInfoPanel = () => {
        const pesoTotal = sortedRoute.reduce((sum, p) => sum + p.peso_total_calculado_kg, 0);
        const distanciaTotal = sortedRoute.reduce((sum, p) => sum + p.distancia_km, 0);
        const tiempoTotal = sortedRoute.reduce((sum, p) => sum + parseInt(p.tiempo_estimado), 0);
        
        selectedCount.textContent = selectedPedidos.size;
        totalWeight.textContent = `${pesoTotal.toFixed(2)}`;
        totalDistance.textContent = `${distanciaTotal.toFixed(1)}`;
        totalTime.textContent = `~${tiempoTotal}`;

        if (vehiculo) {
            capacidadContainer.style.display = 'block';
            const porcentaje = vehiculo.capacidad_kg > 0 ? (pesoTotal / vehiculo.capacidad_kg) * 100 : 0;
            capacidadPorcentaje.textContent = `${porcentaje.toFixed(1)}%`;
            capacidadBar.style.width = `${Math.min(porcentaje, 100)}%`;
            
            if (pesoTotal > vehiculo.capacidad_kg) {
                capacidadBar.classList.add('sobrecarga');
                capacidadAlerta.style.display = 'block';
            } else {
                capacidadBar.classList.remove('sobrecarga');
                capacidadAlerta.style.display = 'none';
            }
        } else {
            capacidadContainer.style.display = 'none';
        }

        ayudaDespacho.style.display = selectedPedidos.size === 0 ? 'block' : 'none';
        
        const sobrecargado = vehiculo && pesoTotal > vehiculo.capacidad_kg;
        confirmarDespachoBtn.disabled = !vehiculo || selectedPedidos.size === 0 || pesoTotal === 0 || sobrecargado;
    };
    
    // --- LÓGICA DE OPTIMIZACIÓN ---
    
    const optimizeRoute = (pedidosToOptimize) => {
        if (pedidosToOptimize.length === 0) return [];
        
        let currentPoint = { latitud: DEPOSITO_COORDS[0], longitud: DEPOSITO_COORDS[1] };
        let remaining = [...pedidosToOptimize];
        const optimized = [];
        
        while (remaining.length > 0) {
            let nearest = null;
            let minDist = Infinity;
            let nearestIndex = -1;

            remaining.forEach((pedido, index) => {
                const dist = Math.sqrt(
                    Math.pow(pedido.direccion.latitud - currentPoint.latitud, 2) +
                    Math.pow(pedido.direccion.longitud - currentPoint.longitud, 2)
                );
                if (dist < minDist) {
                    minDist = dist;
                    nearest = pedido;
                    nearestIndex = index;
                }
            });

            optimized.push(nearest);
            currentPoint = nearest.direccion;
            remaining.splice(nearestIndex, 1);
        }
        return optimized;
    };

    // --- MANEJADORES DE EVENTOS ---
    
    const handlePedidoSelection = (pedidoId) => {
        if (selectedPedidos.has(pedidoId)) {
            selectedPedidos.delete(pedidoId);
        } else {
            selectedPedidos.add(pedidoId);
        }
        
        const selectedPedidosData = pedidosSimulados.filter(p => selectedPedidos.has(p.id));
        sortedRoute = optimizeRoute(selectedPedidosData);
        
        render();
    };

    const handleBuscarVehiculo = async () => {
        const patente = patenteInput.value.trim();
        if (!patente) return;
        
        try {
            const response = await fetch(`/admin/despachos/api/vehiculo/${patente}`);
            const result = await response.json();

            if (result.success) {
                vehiculo = result.data;
                vehiculoInfo.style.display = 'block';
                vehiculoPatente.textContent = vehiculo.patente;
                vehiculoConductor.textContent = vehiculo.nombre_conductor || 'No especificado';
                vehiculoDni.textContent = vehiculo.dni_conductor || 'No especificado';
                vehiculoCapacidad.textContent = vehiculo.capacidad_kg;
            } else {
                vehiculo = null;
                vehiculoInfo.style.display = 'none';
                alert(result.error || 'Vehículo no encontrado');
            }
        } catch (error) {
            console.error('Error buscando vehículo:', error);
            alert('Error de red al buscar el vehículo.');
        }
        updateInfoPanel();
    };
    
    const handleConfirmarDespacho = async () => {
        if (confirmarDespachoBtn.disabled) return;

        const originalButtonHtml = confirmarDespachoBtn.innerHTML;
        confirmarDespachoBtn.disabled = true;
        confirmarDespachoBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            Procesando...
        `;

        const data = {
            vehiculo_id: vehiculo.id,
            pedido_ids: Array.from(selectedPedidos),
            observaciones: observacionesInput.value.trim()
        };

        try {
            const response = await fetch('/admin/despachos/api/crear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();

            if (result.success) {
                // El éxito redirige, no es necesario restaurar el botón.
                window.location.href = result.redirect_url || '/admin/despachos/gestion?tab=historial';
            } else {
                // Mostrar el modal de error
                const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
                document.getElementById('errorModalMessage').textContent = result.error || 'Ocurrió un error desconocido.';
                errorModal.show();

                confirmarDespachoBtn.disabled = false;
                confirmarDespachoBtn.innerHTML = originalButtonHtml;
            }
        } catch (error) {
            console.error('Error al confirmar despacho:', error);
            const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
            document.getElementById('errorModalMessage').textContent = 'Error de conexión o respuesta inesperada del servidor.';
            errorModal.show();
            confirmarDespachoBtn.disabled = false;
            confirmarDespachoBtn.innerHTML = originalButtonHtml;
        }
    };
    
    // --- BINDING DE EVENTOS ---

    viewMapBtn.addEventListener('click', () => {
        viewMode = 'map';
        mapView.classList.add('active');
        listView.classList.remove('active');
        viewMapBtn.classList.add('active');
        viewListBtn.classList.remove('active');
        // Forzar al mapa a recalcular su tamaño
        if(mapInstance) {
            setTimeout(() => mapInstance.invalidateSize(), 100);
        }
    });

    viewListBtn.addEventListener('click', () => {
        viewMode = 'list';
        listView.classList.add('active');
        mapView.classList.remove('active');
        viewListBtn.classList.add('active');
        viewMapBtn.classList.remove('active');
    });
    
    // Usar delegación de eventos para los checkboxes de la tabla de pedidos
    listView.addEventListener('change', (e) => {
        if (e.target.classList.contains('pedido-checkbox')) {
            const id = parseInt(e.target.value, 10);
            handlePedidoSelection(id);
        }
    });
    
    buscarVehiculoBtn.addEventListener('click', handleBuscarVehiculo);
    patenteInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            handleBuscarVehiculo();
        }
    });
    
    confirmarDespachoBtn.addEventListener('click', handleConfirmarDespacho);

    // --- INICIO ---
    const crearDespachoTab = document.getElementById('crear-despacho-tab');
    crearDespachoTab.addEventListener('shown.bs.tab', () => {
        if (!mapInstance) {
            initMap();
            render(); // Renderizar por primera vez después de inicializar el mapa
        } else {
            // Forzar al mapa a recalcular su tamaño si la pestaña se vuelve a mostrar
            setTimeout(() => mapInstance.invalidateSize(), 10);
        }
    });

    // Inicializar si la pestaña ya está activa al cargar la página
    if (crearDespachoTab.classList.contains('active')) {
        initMap();
        render();
    }
});
