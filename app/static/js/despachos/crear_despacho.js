document.addEventListener('DOMContentLoaded', function () {
    const searchBtn = document.getElementById('search-btn');
    const patenteInput = document.getElementById('patente-search');
    const vehicleInfoDiv = document.getElementById('vehicle-info');
    const patenteErrorDiv = document.getElementById('patente-error');
    const confirmBtn = document.getElementById('confirm-despacho-btn');
    const checkboxes = document.querySelectorAll('.pedido-checkbox');
    
    let vehicleData = null;
    let selectedPedidos = new Map();

    // --- Función de ayuda para imprimir HTML ---
    function printHtmlContent(htmlContent) {
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        iframe.contentDocument.write(htmlContent);
        iframe.contentDocument.close();
        iframe.contentWindow.print();
        document.body.removeChild(iframe);
    }

    // --- Búsqueda de Vehículo ---
    searchBtn.addEventListener('click', buscarVehiculo);
    patenteInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            buscarVehiculo();
        }
    });

    async function buscarVehiculo() {
        const patente = patenteInput.value.trim().toUpperCase();
        if (!patente) return;

        patenteInput.classList.remove('is-invalid');
        patenteErrorDiv.textContent = '';

        try {
            const response = await fetch(`/admin/vehiculos/api/buscar?patente=${patente}`);
            const result = await response.json();

            if (result.success && result.data) {
                vehicleData = result.data;
                document.getElementById('vehicle-patente').textContent = `Patente: ${vehicleData.patente}`;
                document.getElementById('vehicle-conductor').textContent = `${vehicleData.nombre_conductor} (DNI: ${vehicleData.dni_conductor})`;
                document.getElementById('vehicle-capacidad').textContent = `${vehicleData.capacidad_kg} kg`;
                document.getElementById('vehicle-id').value = vehicleData.id;
                vehicleInfoDiv.style.display = 'block';
                patenteInput.classList.remove('is-invalid');
                patenteInput.classList.add('is-valid');
            } else {
                vehicleData = null;
                vehicleInfoDiv.style.display = 'none';
                patenteInput.classList.add('is-invalid');
                patenteInput.classList.remove('is-valid');
                patenteErrorDiv.textContent = result.error || 'Vehículo no encontrado.';
            }
        } catch (error) {
            console.error('Error buscando vehículo:', error);
            vehicleData = null;
            vehicleInfoDiv.style.display = 'none';
            patenteInput.classList.add('is-invalid');
            patenteInput.classList.remove('is-valid');
            patenteErrorDiv.textContent = 'Error de red al buscar el vehículo.';
        }
        updateUI();
    }

    // --- Selección de Pedidos ---
    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            const pedidoId = this.value;
            const peso = parseFloat(this.dataset.peso) || 0;

            if (this.checked) {
                selectedPedidos.set(pedidoId, peso);
            } else {
                selectedPedidos.delete(pedidoId);
            }
            updateUI();
        });
    });

    // --- Lógica de UI y Actualización ---
    function updateUI() {
        let totalWeight = 0;
        selectedPedidos.forEach(peso => totalWeight += peso);

        document.getElementById('selected-count').textContent = selectedPedidos.size;
        document.getElementById('total-weight').textContent = totalWeight.toFixed(2);

        const capacityBar = document.getElementById('capacity-bar');
        if (vehicleData && vehicleData.capacidad_kg > 0) {
            const percentage = Math.min((totalWeight / vehicleData.capacidad_kg) * 100, 100);
            capacityBar.style.width = `${percentage}%`;
            
            if (totalWeight > vehicleData.capacidad_kg) {
                capacityBar.classList.add('over-capacity');
            } else {
                capacityBar.classList.remove('over-capacity');
            }
        } else {
            capacityBar.style.width = '0%';
        }

        confirmBtn.disabled = !(vehicleData && selectedPedidos.size > 0);
    }

    // --- Envío del Despacho ---
    confirmBtn.addEventListener('click', async function() {
        if (!vehicleData || selectedPedidos.size === 0) {
            alert('Debe seleccionar un vehículo y al menos un pedido.');
            return;
        }

        const data = {
            vehiculo_id: vehicleData.id,
            pedido_ids: Array.from(selectedPedidos.keys()).map(id => parseInt(id)),
            observaciones: document.getElementById('observaciones').value.trim()
        };
        
        this.disabled = true;
        this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...';
        
        try {
            const response = await fetch('/admin/despachos/api/crear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.success) {
                document.querySelector('.col-lg-8').style.display = 'none';
                
                const successDiv = document.getElementById('success-result');
                const despachoId = result.data.despacho_id;
                
                successDiv.innerHTML = `
                    <div class="alert alert-success">
                        Despacho #${despachoId} creado exitosamente.
                    </div>
                    <div class="d-grid gap-2">
                        <button id="btn-descargar-hoja-ruta" data-despacho-id="${despachoId}" class="btn btn-success">
                            <i class="fas fa-print me-1"></i> Ver/Imprimir Hoja de Ruta
                        </button>
                        <a href="${result.redirect_url}" class="btn btn-secondary">
                            <i class="fas fa-arrow-left me-1"></i> Volver al Listado
                        </a>
                    </div>
                `;
                successDiv.style.display = 'block';

                document.getElementById('btn-descargar-hoja-ruta').addEventListener('click', async function() {
                    this.disabled = true;
                    this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Cargando...';
                    try {
                        const despachoId = this.dataset.despachoId;
                        const response = await fetch(`/admin/despachos/hoja-de-ruta/${despachoId}`);
                        const result = await response.json();
                        if (result.success) {
                            printHtmlContent(result.html);
                        } else {
                            alert('Error: ' + result.error);
                        }
                    } catch (error) {
                        alert('Error de red al generar la hoja de ruta.');
                    } finally {
                        this.disabled = false;
                        this.innerHTML = '<i class="fas fa-print me-1"></i> Ver/Imprimir Hoja de Ruta';
                    }
                });

                confirmBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i> Completado';
                confirmBtn.classList.remove('btn-primary');
                confirmBtn.classList.add('btn-outline-secondary');
                confirmBtn.disabled = true;

            } else {
                alert(`Error: ${result.error || 'No se pudo crear el despacho.'}`);
                this.disabled = false;
                this.innerHTML = '<i class="fas fa-check-circle me-1"></i> Confirmar Despacho';
            }
        } catch (error) {
            console.error('Error al crear despacho:', error);
            alert('Error de red al crear el despacho.');
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-check-circle me-1"></i> Confirmar Despacho';
        }
    });

    // --- Checkbox "Seleccionar Todos" por Localidad ---
    document.querySelectorAll('[id^="select-all-"]').forEach(selectAllCb => {
        selectAllCb.addEventListener('change', function() {
            const tableBody = this.closest('table').querySelector('tbody');
            const localCheckboxes = tableBody.querySelectorAll('.pedido-checkbox');
            localCheckboxes.forEach(cb => {
                if (cb.checked !== this.checked) {
                    cb.checked = this.checked;
                    cb.dispatchEvent(new Event('change'));
                }
            });
        });
    });
});
