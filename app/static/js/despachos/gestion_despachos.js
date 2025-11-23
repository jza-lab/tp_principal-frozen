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
    const suggestionsList = document.getElementById('suggestions-list');
    
    const vehiculoInfo = document.getElementById('vehiculo-info');
    const vehiculoPatente = document.getElementById('vehiculo-patente');
    const vehiculoConductor = document.getElementById('vehiculo-conductor');
    const vehiculoDni = document.getElementById('vehiculo-dni');
    const vehiculoCapacidad = document.getElementById('vehiculo-capacidad');
    
    // Docs references
    const vehiculoVtvVenc = document.getElementById('vehiculo-vtv-venc');
    const vehiculoVtvEmision = document.getElementById('vehiculo-vtv-emision');
    const vehiculoVtvBadge = document.getElementById('vehiculo-vtv-badge');
    const vehiculoLicenciaVenc = document.getElementById('vehiculo-licencia-venc');
    const vehiculoLicenciaEmision = document.getElementById('vehiculo-licencia-emision');
    const vehiculoLicenciaBadge = document.getElementById('vehiculo-licencia-badge');

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
    
    let debounceTimer;

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
        document.querySelectorAll('#list-view .pedido-checkbox').forEach(checkbox => {
            const pedidoId = parseInt(checkbox.value, 10);
            const row = checkbox.closest('tr');
            if (row) {
                if (selectedPedidos.has(pedidoId)) {
                    checkbox.checked = true;
                    row.classList.add('table-primary');
                } else {
                    checkbox.checked = false;
                    row.classList.remove('table-primary');
                }
            }
        });

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

        let docsVencidos = false;

        if (vehiculo) {
            // Chequeo de documentos vencidos (segunda capa de seguridad frontend)
            if (vehiculo.estado_vtv === 'VENCIDA' || vehiculo.estado_licencia === 'VENCIDA') {
                docsVencidos = true;
            }

            capacidadContainer.style.display = 'block';
            const porcentaje = vehiculo.capacidad_kg > 0 ? (pesoTotal / vehiculo.capacidad_kg) * 100 : 0;
            capacidadPorcentaje.textContent = `${porcentaje.toFixed(1)}%`;
            capacidadBar.style.width = `${Math.min(porcentaje, 100)}%`;
            
            if (pesoTotal > vehiculo.capacidad_kg) {
                capacidadBar.classList.add('sobrecarga');
                capacidadAlerta.style.display = 'block';
                capacidadAlerta.textContent = "⚠️ Excede la capacidad del vehículo";
            } else {
                capacidadBar.classList.remove('sobrecarga');
                capacidadAlerta.style.display = 'none';
            }
            
            if (docsVencidos) {
                capacidadAlerta.style.display = 'block';
                capacidadAlerta.textContent = "🚫 Documentación VENCIDA. No se puede asignar.";
                capacidadAlerta.classList.add('text-danger', 'fw-bold'); // Ensure visibility
            }

        } else {
            capacidadContainer.style.display = 'none';
        }

        ayudaDespacho.style.display = selectedPedidos.size === 0 ? 'block' : 'none';
        
        const sobrecargado = vehiculo && pesoTotal > vehiculo.capacidad_kg;
        confirmarDespachoBtn.disabled = !vehiculo || selectedPedidos.size === 0 || pesoTotal === 0 || sobrecargado || docsVencidos;
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

    // --- NUEVA LÓGICA DE BÚSQUEDA ---
    const renderVehicleInfo = (data) => {
         vehiculo = data;
         vehiculoInfo.style.display = 'block';
         vehiculoPatente.textContent = vehiculo.patente;
         vehiculoConductor.textContent = vehiculo.nombre_conductor || 'No especificado';
         vehiculoDni.textContent = vehiculo.dni_conductor || 'No especificado';
         vehiculoCapacidad.textContent = vehiculo.capacidad_kg;
         
         // Helper para badges
         const getBadge = (estado, texto) => {
             if (estado === 'VENCIDA') return `<span class="badge bg-danger doc-badge mt-1">VENCIDA</span>`;
             if (estado === 'PRONTO_VENC') return `<span class="badge bg-warning text-dark doc-badge mt-1">PRONTO VENC.</span>`;
             return `<span class="badge bg-success doc-badge mt-1">AL DÍA</span>`;
         };

         // Docs VTV
        if (vehiculo.vtv_vencimiento) {
            vehiculoVtvVenc.textContent = vehiculo.vtv_vencimiento;
            vehiculoVtvEmision.textContent = vehiculo.vtv_emision_estimada || '-';
            vehiculoVtvBadge.outerHTML = `<span id="vehiculo-vtv-badge">${getBadge(vehiculo.estado_vtv)}</span>`;
            // Recapturar referencia tras replace
            const badge = document.getElementById('vehiculo-vtv-badge');
            badge.className = 'badge doc-badge mt-1';
            if(vehiculo.estado_vtv === 'VENCIDA') {
                badge.classList.add('bg-danger');
                badge.textContent = 'VENCIDA';
            } else if (vehiculo.estado_vtv === 'PRONTO_VENC') {
                badge.classList.add('bg-warning', 'text-dark');
                badge.textContent = 'PRONTO VENC.';
            } else {
                badge.classList.add('bg-success');
                badge.textContent = 'AL DÍA';
            }
        } else {
            vehiculoVtvVenc.textContent = '-';
            vehiculoVtvEmision.textContent = '-';
            const badge = document.getElementById('vehiculo-vtv-badge');
            badge.className = 'badge bg-secondary doc-badge mt-1';
            badge.textContent = 'N/A';
        }

        // Docs Licencia
        if (vehiculo.licencia_vencimiento) {
            vehiculoLicenciaVenc.textContent = vehiculo.licencia_vencimiento;
            vehiculoLicenciaEmision.textContent = vehiculo.licencia_emision_estimada || '-';
             const badge = document.getElementById('vehiculo-licencia-badge');
             badge.className = 'badge doc-badge mt-1';
            if(vehiculo.estado_licencia === 'VENCIDA') {
                badge.classList.add('bg-danger');
                badge.textContent = 'VENCIDA';
            } else if (vehiculo.estado_licencia === 'PRONTO_VENC') {
                badge.classList.add('bg-warning', 'text-dark');
                badge.textContent = 'PRONTO VENC.';
            } else {
                badge.classList.add('bg-success');
                badge.textContent = 'AL DÍA';
            }
        } else {
            vehiculoLicenciaVenc.textContent = '-';
            vehiculoLicenciaEmision.textContent = '-';
            const badge = document.getElementById('vehiculo-licencia-badge');
            badge.className = 'badge bg-secondary doc-badge mt-1';
            badge.textContent = 'N/A';
        }
         
         updateInfoPanel();
    };

    const fetchSuggestions = async (query) => {
        try {
            // Si query es vacío o corto, podríamos traer todos o los últimos usados
            const url = query ? `/admin/vehiculos/api/buscar?search=${encodeURIComponent(query)}` : `/admin/vehiculos/api/buscar?search=`; 
            
            const response = await fetch(url);
            const data = await response.json();
            suggestionsList.innerHTML = '';
            
            if (data.success && data.data && data.data.length > 0) {
                data.data.forEach(v => {
                    const item = document.createElement('div');
                    item.className = 'suggestion-item';
                    item.innerHTML = `<strong>${v.patente}</strong> - ${v.nombre_conductor}`;
                    item.addEventListener('click', () => {
                        patenteInput.value = v.patente;
                        renderVehicleInfo(v);
                        suggestionsList.style.display = 'none';
                    });
                    suggestionsList.appendChild(item);
                });
                suggestionsList.style.display = 'block';
            } else {
                const item = document.createElement('div');
                item.className = 'suggestion-item text-muted';
                item.textContent = 'No se encontraron vehículos válidos.';
                suggestionsList.appendChild(item);
                suggestionsList.style.display = 'block';
            }
        } catch (error) {
            console.error(error);
        }
    };

    if (patenteInput) {
        // Cargar todos al hacer foco si está vacío
        patenteInput.addEventListener('focus', function() {
            if(!this.value) {
                fetchSuggestions('');
            }
        });

        patenteInput.addEventListener('input', function() {
            const query = this.value.trim();
            clearTimeout(debounceTimer);
            
            // Permitir búsqueda vacía (reset) o búsqueda por término
            debounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 300);
        });
        
        // Hide on outside click
        document.addEventListener('click', (e) => {
            if (!patenteInput.contains(e.target) && !suggestionsList.contains(e.target)) {
                suggestionsList.style.display = 'none';
            }
        });
    }

    // --- MODAL NUEVO VEHÍCULO ---
    const modalElement = document.getElementById('nuevoVehiculoModal');
    if (modalElement) {
        const modalForm = document.getElementById('form-nuevo-vehiculo');
        const btnGuardar = document.getElementById('btn-guardar-vehiculo');
        const errorAlert = document.getElementById('modal-error-alert');
        
        // Elementos dinámicos
        const modalTipo = document.getElementById('modal_tipo');
        const modalCapacidad = document.getElementById('modal_capacidad');
        const modalCapacidadHelp = document.getElementById('modal-capacidad-help');
        
        // Rangos de capacidad
        const capacityRanges = {
            "Camioneta / Utilitario": { min: 600, max: 1000 },
            "Combi / Furgon": { min: 1500, max: 2500 },
            "Camión (Liviano)": { min: 3500, max: 6000 }
        };
        
        // Update capacity logic for Modal
        if (modalTipo && modalCapacidad) {
            modalTipo.addEventListener('change', () => {
                const selectedType = modalTipo.value;
                const range = capacityRanges[selectedType];
                
                if (range) {
                    modalCapacidad.min = range.min;
                    modalCapacidad.max = range.max;
                    modalCapacidadHelp.textContent = `Rango permitido: ${range.min} - ${range.max} kg.`;
                    
                    // Validar si ya hay valor
                    if (modalCapacidad.value) {
                         const val = parseFloat(modalCapacidad.value);
                         if (val < range.min || val > range.max) {
                             modalCapacidad.setCustomValidity(`Debe estar entre ${range.min} y ${range.max} kg.`);
                         } else {
                             modalCapacidad.setCustomValidity('');
                         }
                    }
                } else {
                    modalCapacidad.removeAttribute('min');
                    modalCapacidad.removeAttribute('max');
                    modalCapacidadHelp.textContent = 'Seleccione un tipo de vehículo.';
                    modalCapacidad.setCustomValidity('');
                }
            });
            
            modalCapacidad.addEventListener('input', () => {
                const selectedType = modalTipo.value;
                const range = capacityRanges[selectedType];
                if(range) {
                     const val = parseFloat(modalCapacidad.value);
                     if (val < range.min || val > range.max) {
                         modalCapacidad.setCustomValidity(`Debe estar entre ${range.min} y ${range.max} kg.`);
                     } else {
                         modalCapacidad.setCustomValidity('');
                     }
                }
            });
        }

        // Función auxiliar validación frontend
        const validateForm = () => {
            const dni = document.getElementById('modal_dni').value;
            const tel = document.getElementById('modal_telefono').value;
            const tipo = modalTipo.value;
            
            if (dni && !/^\d{7,8}$/.test(dni)) {
                return "El DNI debe tener 7 u 8 dígitos numéricos.";
            }
            if (tel && !/^\d{7,}$/.test(tel)) {
                return "El teléfono debe tener al menos 7 dígitos numéricos.";
            }
            if (!tipo) {
                return "Debe seleccionar un tipo de vehículo.";
            }
            return null;
        };

        btnGuardar.addEventListener('click', async function() {
            errorAlert.classList.add('d-none');
            errorAlert.textContent = '';
            
            // Forzar validación de capacidad si está seteada la customValidity
            if (!modalForm.checkValidity()) {
                modalForm.reportValidity();
                return;
            }

            // Validación JS extra
            const errorMsg = validateForm();
            if (errorMsg) {
                errorAlert.textContent = errorMsg;
                errorAlert.classList.remove('d-none');
                return;
            }

            const formData = new FormData(modalForm);
            
            try {
                const response = await fetch('/admin/vehiculos/nuevo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
                    body: new URLSearchParams(formData)
                });
                
                if (response.redirected) {
                     // Éxito por redirect
                     if (typeof showNotificationModal === 'function') {
                         showNotificationModal('Éxito', 'Vehículo creado correctamente.', 'success');
                     }
                     const modal = bootstrap.Modal.getInstance(modalElement);
                     modal.hide();
                     
                     const nuevaPatente = formData.get('patente');
                     patenteInput.value = nuevaPatente;
                     const searchRes = await fetch(`/admin/vehiculos/api/buscar?search=${nuevaPatente}`);
                     const searchData = await searchRes.json();
                     if (searchData.success && searchData.data && searchData.data.length > 0) {
                         renderVehicleInfo(searchData.data[0]);
                     }
                } else {
                     // Intentar leer como JSON primero si el content-type es json
                     const contentType = response.headers.get("content-type");
                     if (contentType && contentType.includes("application/json")) {
                         const data = await response.json();
                         if (data.error) {
                             errorAlert.textContent = data.error;
                             errorAlert.classList.remove('d-none');
                         } else {
                             errorAlert.textContent = "Error desconocido.";
                             errorAlert.classList.remove('d-none');
                         }
                     } else {
                         // Fallback para HTML legacy
                         const text = await response.text();
                         if (text.includes('alert-danger')) {
                             errorAlert.textContent = "Error al crear el vehículo. Verifique que la patente no exista ya o los datos sean válidos.";
                             errorAlert.classList.remove('d-none');
                         } else {
                             errorAlert.textContent = "Error al procesar la solicitud.";
                             errorAlert.classList.remove('d-none');
                         }
                     }
                }
            } catch (err) {
                console.error(err);
                errorAlert.textContent = 'Error de conexión.';
                errorAlert.classList.remove('d-none');
            }
        });
    }

    const handleConfirmarDespacho = async () => {
        if (confirmarDespachoBtn.disabled) return;
        const originalButtonHtml = confirmarDespachoBtn.innerHTML;
        confirmarDespachoBtn.disabled = true;
        confirmarDespachoBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...`;

        const data = {
            vehiculo_id: vehiculo.id,
            pedido_ids: Array.from(selectedPedidos),
            observaciones: observacionesInput.value.trim()
        };

        try {
            const response = await fetch('/admin/despachos/api/crear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.success) {
                window.location.href = result.redirect_url || '/admin/despachos/gestion?tab=historial';
            } else {
                const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
                document.getElementById('errorModalMessage').textContent = result.error || 'Ocurrió un error desconocido.';
                errorModal.show();
                confirmarDespachoBtn.disabled = false;
                confirmarDespachoBtn.innerHTML = originalButtonHtml;
            }
        } catch (error) {
            console.error('Error al confirmar despacho:', error);
            const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
            document.getElementById('errorModalMessage').textContent = 'Error de conexión.';
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
        if(mapInstance) setTimeout(() => mapInstance.invalidateSize(), 100);
    });

    viewListBtn.addEventListener('click', () => {
        viewMode = 'list';
        listView.classList.add('active');
        mapView.classList.remove('active');
        viewListBtn.classList.add('active');
        viewMapBtn.classList.remove('active');
    });
    
    listView.addEventListener('change', (e) => {
        if (e.target.classList.contains('pedido-checkbox')) {
            const id = parseInt(e.target.value, 10);
            handlePedidoSelection(id);
        }
    });
    
    confirmarDespachoBtn.addEventListener('click', handleConfirmarDespacho);

    const crearDespachoTab = document.getElementById('crear-despacho-tab');
    crearDespachoTab.addEventListener('shown.bs.tab', () => {
        if (!mapInstance) {
            initMap();
            render();
        } else {
            setTimeout(() => mapInstance.invalidateSize(), 10);
        }
    });

    if (crearDespachoTab.classList.contains('active')) {
        initMap();
        render();
    }
});
