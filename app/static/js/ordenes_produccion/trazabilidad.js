document.addEventListener('DOMContentLoaded', function() {
    const trazabilidadModal = new bootstrap.Modal(document.getElementById('trazabilidadModal'));
    const modalBody = document.getElementById('trazabilidadModalBody');
    const modalTitle = document.getElementById('trazabilidadModalLabel');

    document.querySelectorAll('.btn-trazabilidad').forEach(button => {
        button.addEventListener('click', function() {
            const opId = this.dataset.opId;
            
            // 1. Reset modal content to loading state and show
            modalTitle.textContent = `Trazabilidad de la Orden de Producción #${opId}`;
            modalBody.innerHTML = `
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos de trazabilidad...</p>
                </div>`;
            trazabilidadModal.show();

            // 2. Fetch data from the API
            fetch(`/api/orden_produccion/${opId}/trazabilidad`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('La respuesta de la red no fue exitosa.');
                    }
                    return response.json();
                })
                .then(result => {
                    if (result.success) {
                        // 3. Build and render the HTML content
                        renderTrazabilidad(result.data);
                    } else {
                        throw new Error(result.error || 'Error al obtener los datos de trazabilidad.');
                    }
                })
                .catch(error => {
                    // 4. Handle errors
                    modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
                });
        });
    });

    function renderTrazabilidad(data) {
        const op = data.orden_produccion;
        const upstream = data.upstream;
        const downstream = data.downstream;

        const upstreamHtml = upstream.insumos.length > 0 ? upstream.insumos.map(insumo => `
            <tr>
                <td>${insumo.nombre_insumo}</td>
                <td>${insumo.lote_insumo}</td>
                <td>${insumo.cantidad_usada}</td>
                <td>${insumo.proveedor}</td>
            </tr>
        `).join('') : '<tr><td colspan="4" class="text-center">No se utilizaron insumos directos.</td></tr>';

        const downstreamLotesHtml = downstream.lotes_producidos.length > 0 ? downstream.lotes_producidos.map(lote => `
            <tr>
                <td>${lote.numero_lote}</td>
                <td>${lote.cantidad_producida}</td>
            </tr>
        `).join('') : '<tr><td colspan="2" class="text-center">No se generaron lotes.</td></tr>';

        const downstreamPedidosHtml = downstream.pedidos.length > 0 ? downstream.pedidos.map(pedido => `
            <tr>
                <td>${pedido.codigo_pedido}</td>
                <td>${pedido.cliente}</td>
                <td>${pedido.fecha_entrega}</td>
            </tr>
        `).join('') : '<tr><td colspan="3" class="text-center">No se encontraron pedidos asociados.</td></tr>';

        const responsables = data.responsables;

        modalBody.innerHTML = `
            <div class="row">
                <!-- Columna Central: Orden de Producción -->
                <div class="col-12 text-center mb-4">
                    <div class="card bg-light">
                        <div class="card-body">
                            <h5 class="card-title">Orden de Producción: ${op.codigo}</h5>
                            <p class="card-text"><strong>Producto:</strong> ${op.producto}</p>
                            <p class="card-text"><strong>Cantidad:</strong> ${op.cantidad_planificada}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <!-- Columna Izquierda: Upstream -->
                <div class="col-md-6">
                    <h5 class="text-center"><i class="bi bi-arrow-up-circle-fill text-primary"></i> Upstream (Origen)</h5>
                    <div class="card">
                        <div class="card-body">
                            <h6>Insumos Utilizados</h6>
                            <table class="table table-sm">
                                <thead><tr><th>Insumo</th><th>Lote</th><th>Cantidad</th><th>Proveedor</th></tr></thead>
                                <tbody>${upstreamHtml}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Columna Derecha: Downstream -->
                <div class="col-md-6">
                    <h5 class="text-center"><i class="bi bi-arrow-down-circle-fill text-success"></i> Downstream (Destino)</h5>
                    <div class="card">
                        <div class="card-body">
                            <h6>Lotes Producidos</h6>
                            <table class="table table-sm">
                                <thead><tr><th>N° Lote</th><th>Cantidad</th></tr></thead>
                                <tbody>${downstreamLotesHtml}</tbody>
                            </table>
                            <hr>
                            <h6>Pedidos Asociados</h6>
                            <table class="table table-sm">
                                <thead><tr><th>Pedido</th><th>Cliente</th><th>Fecha Entrega</th></tr></thead>
                                <tbody>${downstreamPedidosHtml}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Fila de Responsables -->
            <div class="row mt-4">
                <div class="col-12">
                    <h5 class="text-center"><i class="bi bi-people-fill text-info"></i> Responsables</h5>
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-around text-center">
                                <div>
                                    <p class="mb-0 text-muted">Vendedor</p>
                                    <strong>${responsables.vendedor || 'N/A'}</strong>
                                </div>
                                <div>
                                    <p class="mb-0 text-muted">Supervisor</p>
                                    <strong>${responsables.supervisor || 'N/A'}</strong>
                                </div>
                                <div>
                                    <p class="mb-0 text-muted">Operario</p>
                                    <strong>${responsables.operario || 'N/A'}</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
});
