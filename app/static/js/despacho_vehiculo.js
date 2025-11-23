document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('buscar-patente');
    const suggestionsList = document.getElementById('suggestions-list');
    const newVehicleButton = document.getElementById('btn-nuevo-vehiculo');
    
    // Contenedor de Detalles
    const detailsContainer = document.getElementById('vehicle-details-container');
    const detailPatente = document.getElementById('detail-patente');
    const detailConductor = document.getElementById('detail-conductor');
    const detailDni = document.getElementById('detail-dni');
    const detailCapacidad = document.getElementById('detail-capacidad');
    
    // Detalles Documentación
    const detailVtvVenc = document.getElementById('detail-vtv-venc');
    const detailVtvEmision = document.getElementById('detail-vtv-emision');
    const detailVtvBadge = document.getElementById('detail-vtv-badge');
    const detailLicenciaVenc = document.getElementById('detail-licencia-venc');
    const detailLicenciaEmision = document.getElementById('detail-licencia-emision');
    const detailLicenciaBadge = document.getElementById('detail-licencia-badge');

    // Inputs ocultos para submit
    const inputConductorNombre = document.getElementById('conductor_nombre');
    const inputConductorDni = document.getElementById('conductor_dni');
    const inputConductorTelefono = document.getElementById('conductor_telefono');
    const inputVehiculoTipo = document.getElementById('vehiculo_tipo');
    const inputVehiculoPatente = document.getElementById('vehiculo_patente');

    let debounceTimer;

    function selectVehicle(vehiculo) {
        // Llenar inputs ocultos
        inputConductorNombre.value = vehiculo.nombre_conductor;
        inputConductorDni.value = vehiculo.dni_conductor;
        inputConductorTelefono.value = vehiculo.telefono_conductor || '';
        inputVehiculoTipo.value = vehiculo.tipo_vehiculo || '';
        inputVehiculoPatente.value = vehiculo.patente;

        // Mostrar detalles visuales
        detailPatente.textContent = vehiculo.patente;
        detailConductor.textContent = vehiculo.nombre_conductor;
        detailDni.textContent = vehiculo.dni_conductor;
        detailCapacidad.textContent = (vehiculo.capacidad_kg || '-') + ' kg';

        // Documentación VTV
        if (vehiculo.vtv_vencimiento) {
            detailVtvVenc.textContent = vehiculo.vtv_vencimiento;
            detailVtvEmision.textContent = vehiculo.vtv_emision_estimada || '-';
            if (vehiculo.alerta_vtv) {
                detailVtvBadge.className = 'badge bg-danger mt-1';
                detailVtvBadge.textContent = 'Vencida / Por Vencer';
            } else {
                detailVtvBadge.className = 'badge bg-success mt-1';
                detailVtvBadge.textContent = 'Al día';
            }
        } else {
            detailVtvVenc.textContent = '-';
            detailVtvEmision.textContent = '-';
            detailVtvBadge.className = 'badge bg-secondary mt-1';
            detailVtvBadge.textContent = 'No Reg.';
        }

        // Documentación Licencia
        if (vehiculo.licencia_vencimiento) {
            detailLicenciaVenc.textContent = vehiculo.licencia_vencimiento;
            detailLicenciaEmision.textContent = vehiculo.licencia_emision_estimada || '-';
            if (vehiculo.alerta_licencia) {
                detailLicenciaBadge.className = 'badge bg-danger mt-1';
                detailLicenciaBadge.textContent = 'Vencida / Por Vencer';
            } else {
                detailLicenciaBadge.className = 'badge bg-success mt-1';
                detailLicenciaBadge.textContent = 'Al día';
            }
        } else {
            detailLicenciaVenc.textContent = '-';
            detailLicenciaEmision.textContent = '-';
            detailLicenciaBadge.className = 'badge bg-secondary mt-1';
            detailLicenciaBadge.textContent = 'No Reg.';
        }

        // Mostrar contenedor, ocultar sugerencias, poner patente en input
        detailsContainer.classList.remove('d-none');
        suggestionsList.style.display = 'none';
        searchInput.value = vehiculo.patente;
    }

    async function fetchSuggestions(query) {
        try {
            const response = await fetch(`/admin/vehiculos/api/buscar?search=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            suggestionsList.innerHTML = '';
            
            if (data.success && data.data && data.data.length > 0) {
                data.data.forEach(vehiculo => {
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action';
                    item.innerHTML = `
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 fw-bold">${vehiculo.patente}</h6>
                            <small>${vehiculo.tipo_vehiculo || ''}</small>
                        </div>
                        <p class="mb-1 small text-muted">Cond: ${vehiculo.nombre_conductor}</p>
                    `;
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        selectVehicle(vehiculo);
                    });
                    suggestionsList.appendChild(item);
                });
                suggestionsList.style.display = 'block';
            } else {
                // No hay resultados
                const item = document.createElement('div');
                item.className = 'list-group-item text-muted small';
                item.textContent = 'No se encontraron vehículos. Cree uno nuevo.';
                suggestionsList.appendChild(item);
                suggestionsList.style.display = 'block';
            }
        } catch (error) {
            console.error(error);
        }
    }

    if (searchInput) {
        // Evento click/focus: Mostrar todos si está vacío
        searchInput.addEventListener('focus', function() {
             const query = this.value.trim();
             // Si el campo está vacio (o tiene algo), disparamos la búsqueda
             // para que el usuario vea las opciones inmediatamente.
             fetchSuggestions(query);
        });

        searchInput.addEventListener('input', function() {
            const query = this.value.trim();
            
            clearTimeout(debounceTimer);
            
            // Se eliminó la restricción de query.length < 2 para permitir
            // borrar y ver toda la lista de nuevo, o buscar por 1 letra.

            debounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 300); // 300ms debounce
        });

        // Ocultar sugerencias al hacer click fuera
        document.addEventListener('click', function(e) {
            if (!searchInput.contains(e.target) && !suggestionsList.contains(e.target)) {
                suggestionsList.style.display = 'none';
            }
        });
    }

    // --- Modal Nuevo Vehículo ---
    const modalElement = document.getElementById('nuevoVehiculoModal');
    if (modalElement) {
        const modalForm = document.getElementById('form-nuevo-vehiculo');
        const btnGuardar = document.getElementById('btn-guardar-vehiculo');
        
        btnGuardar.addEventListener('click', async function() {
            const formData = new FormData(modalForm);
            
            // Validacion simple
            if (!formData.get('patente') || !formData.get('nombre_conductor')) {
                alert('Complete Patente y Conductor.');
                return;
            }

            try {
                const response = await fetch('/admin/vehiculos/nuevo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
                    body: new URLSearchParams(formData)
                });
                
                if (response.redirected || response.ok) {
                     alert('Vehículo creado.');
                     const modal = bootstrap.Modal.getInstance(modalElement);
                     modal.hide();
                     
                     // Buscar el vehiculo recien creado para obtener datos procesados (fechas)
                     // Usamos la patente que acabamos de meter
                     const nuevaPatente = formData.get('patente');
                     searchInput.value = nuevaPatente;
                     // Forzar búsqueda exacta (simulada via search)
                     const searchRes = await fetch(`/admin/vehiculos/api/buscar?search=${nuevaPatente}`);
                     const searchData = await searchRes.json();
                     
                     if (searchData.success && searchData.data && searchData.data.length > 0) {
                         // Asumimos que el primero es el match (patente unica)
                         selectVehicle(searchData.data[0]);
                     }

                } else {
                     alert('Error al crear vehiculo.');
                }
            } catch (err) {
                console.error(err);
                alert('Error de conexión.');
            }
        });
        
        // Pre-llenar si escribimos algo en el buscador
        modalElement.addEventListener('show.bs.modal', function () {
             const val = searchInput.value.trim();
             if (val && val.length > 3) { // Solo si parece una patente
                 modalElement.querySelector('input[name="patente"]').value = val;
             }
        });
    }
});
