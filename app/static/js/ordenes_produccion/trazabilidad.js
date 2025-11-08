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
        // Compatibilidad para ambas estructuras de datos
        const resumen = data.resumen || {};
        const opData = data.orden_produccion || (resumen.origen ? resumen.origen.op : {});
        const upstreamData = data.upstream || (resumen.origen ? { insumos: resumen.origen.insumos } : { insumos: [] });
        const downstreamData = data.downstream || (resumen.destino ? { lotes_producidos: resumen.destino.lotes, pedidos: resumen.destino.pedidos } : { lotes_producidos: [], pedidos: [] });
        const ocsAsociadasData = resumen.ordenes_compra_asociadas || [];
        const responsablesData = data.responsables || {};


        // --- HTML para Insumos Utilizados ---
        const upstreamHtml = upstreamData.insumos.length > 0 ? upstreamData.insumos.map(insumo => `
            <tr>
                <td>${insumo.nombre_insumo || insumo.nombre}</td>
                <td><a href="/inventario/lote/${insumo.id_lote_insumo || insumo.id}" target="_blank">${insumo.lote_insumo || 'Ver Lote'}</a></td>
                <td>${insumo.cantidad_usada || insumo.cantidad}</td>
                <td><a href="/proveedores/${insumo.id_proveedor}/ordenes_compra" target="_blank">${insumo.proveedor || 'N/A'}</a></td>
            </tr>
        `).join('') : '<tr><td colspan="4" class="text-center text-muted">No se utilizaron insumos directos.</td></tr>';

        // --- HTML para Órdenes de Compra Asociadas ---
        const ocsAsociadasHtml = ocsAsociadasData.length > 0 ? ocsAsociadasData.map(oc => {
            let fechaHtml = `<small class="text-muted">Est: ${oc.fecha_estimada_entrega || 'N/D'}</small>`;
            if (oc.fecha_real_entrega) {
                fechaHtml += `<br><small class="text-muted">Real: ${oc.fecha_real_entrega}</small>`;
            }
            return `
            <div class="card mb-2 shadow-sm">
                <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <a href="/compras/detalle/${oc.id}" class="fw-bold" target="_blank">${oc.codigo_oc}</a>
                            <span class="badge bg-warning text-dark ms-2">${oc.estado}</span>
                        </div>
                        <div class="text-end">
                            ${fechaHtml}
                        </div>
                    </div>
                    <p class="mb-1 small">
                        Proveedor: <a href="/proveedores/${oc.proveedor_id}/ordenes_compra" target="_blank">${oc.proveedor_nombre}</a>
                    </p>
                    <ul class="list-unstyled mb-0 small">
                        ${oc.items.map(item => `<li>- ${item.cantidad_solicitada} x ${item.nombre_insumo}</li>`).join('')}
                    </ul>
                </div>
            </div>
        `}).join('') : '<p class="text-center text-muted">No hay órdenes de compra asociadas.</p>';


        // --- HTML para Lotes Producidos ---
        const downstreamLotesHtml = downstreamData.lotes_producidos.length > 0 ? downstreamData.lotes_producidos.map(lote => `
            <tr>
                <td><a href="/lotes-productos/${lote.id}/detalle" target="_blank">${lote.numero_lote || lote.codigo}</a></td>
                <td>${lote.cantidad_producida || lote.cantidad}</td>
            </tr>
        `).join('') : '<tr><td colspan="2" class="text-center text-muted">No se generaron lotes.</td></tr>';
        
        // --- HTML para Pedidos Asociados ---
        const downstreamPedidosHtml = downstreamData.pedidos.length > 0 ? downstreamData.pedidos.map(pedido => `
            <tr>
                <td><a href="/orden-venta/${pedido.id}/detalle" target="_blank">${pedido.codigo_pedido || `PED-${pedido.id}`}</a></td>
                <td>${pedido.cliente || 'N/A'}</td>
                <td>${pedido.fecha_entrega || 'N/D'}</td>
            </tr>
        `).join('') : '<tr><td colspan="3" class="text-center text-muted">No se encontraron pedidos asociados.</td></tr>';

        // --- Renderizado Final ---
        modalBody.innerHTML = `
            <div class="row">
                <div class="col-12 text-center mb-4">
                    <div class="card bg-light border-0">
                        <div class="card-body">
                            <h5 class="card-title">Orden de Producción: ${opData.codigo}</h5>
                            <p class="card-text mb-0"><strong>Producto:</strong> ${opData.producto || opData.producto_nombre}</p>
                            <p class="card-text mb-0"><strong>Cantidad:</strong> ${opData.cantidad_planificada}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <!-- Upstream -->
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-primary text-white"><i class="bi bi-arrow-up-circle-fill"></i> Origen (Upstream)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Insumos Utilizados</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>Insumo</th><th>Lote</th><th>Cantidad</th><th>Proveedor</th></tr></thead>
                                    <tbody>${upstreamHtml}</tbody>
                                </table>
                            </div>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Órdenes de Compra Asociadas</h6>
                            ${ocsAsociadasHtml}
                        </div>
                    </div>
                </div>

                <!-- Downstream -->
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white"><i class="bi bi-arrow-down-circle-fill"></i> Destino (Downstream)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Lotes Producidos</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>N° Lote</th><th>Cantidad</th></tr></thead>
                                    <tbody>${downstreamLotesHtml}</tbody>
                                </table>
                            </div>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Pedidos de Cliente Asociados</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>Pedido</th><th>Cliente</th><th>Fecha Entrega</th></tr></thead>
                                    <tbody>${downstreamPedidosHtml}</tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Responsables -->
            <div class="row mt-2">
                <div class="col-12">
                    <div class="card">
                         <div class="card-header bg-info text-white"><i class="bi bi-people-fill"></i> Responsables</div>
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-around text-center">
                                <div>
                                    <p class="mb-0 text-muted small">Supervisor/es de calidad</p>
                                    <strong>${responsablesData.supervisor_calidad || 'N/A'}</strong>
                                </div>
                                <div>
                                    <p class="mb-0 text-muted small">Operario/s</p>
                                    <strong>${responsablesData.operario || 'N/A'}</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
});
