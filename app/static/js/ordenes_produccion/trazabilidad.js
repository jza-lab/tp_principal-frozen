document.addEventListener('DOMContentLoaded', function() {
    const trazabilidadModal = new bootstrap.Modal(document.getElementById('trazabilidadModal'));
    const modalBody = document.getElementById('trazabilidadModalBody');
    const modalTitle = document.getElementById('trazabilidadModalLabel');

    document.querySelectorAll('.btn-trazabilidad').forEach(button => {
        button.addEventListener('click', function() {
            const opId = this.dataset.opId;
            
            // 1. Reset modal content to loading state (Estilo de trazabilidad (1).js)
            modalTitle.textContent = `Trazabilidad de la Orden de Producción #${opId}`;
            modalBody.innerHTML = `
                <div class="text-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos de trazabilidad...</p>
                </div>`;
            trazabilidadModal.show();

            // 2. Fetch data (Lógica de trazabilidad.js - SE MANTIENE)
            fetch(`/api/trazabilidad/orden_produccion/${opId}?nivel=simple`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('La respuesta de la red no fue exitosa.');
                    }
                    return response.json();
                })
                .then(result => {
                    if (result.success && result.data) {
                        // 3. Build and render HTML
                        renderTrazabilidad(result.data.resumen, opId);
                    } else {
                        throw new Error(result.error || 'No se pudieron obtener los datos.');
                    }
                })
                .catch(error => {
                    // 4. Handle errors
                    modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
                });
        });
    });

    /**
     * Renderiza el contenido del modal
     */
    function renderTrazabilidad(resumen, opId) {
        
        // --- 1. Data Extraction (Lógica de trazabilidad.js) ---
        const origen = resumen.origen || [];
        const destino = resumen.destino || [];

        // --- Extracción de datos detallados de OC ---
        // Se asume que la API 'simple' ahora provee esta estructura 
        // (similar a como lo hacía trazabilidad (1).js)
        const ocsAsociadasData = resumen.ordenes_compra_asociadas || [];

        // --- Extracción de datos simples para lo demás ---
        const insumos = origen.filter(item => item.tipo === 'lote_insumo');
        const lotesProducto = destino.filter(item => item.tipo === 'lote_producto');
        const pedidos = destino.filter(item => item.tipo === 'pedido');

        // --- 2. HTML Generation ---

        // --- HTML para Insumos Utilizados (Se mantiene estilo 'simple') ---
        const upstreamHtml = insumos.length > 0 ? insumos.map(insumo => `
            <tr>
                <td>${insumo.nombre}</td>
                <td><a href="/inventario/lote/${insumo.id}" target="_blank">Ver Lote (ID: ${insumo.id})</a></td>
                <td>${insumo.detalle}</td>
                <td class="text-muted">N/A</td> 
            </tr>
        `).join('') : '<tr><td colspan="4" class="text-center text-muted">No se utilizaron insumos directos.</td></tr>';

        // --- HTML para Órdenes de Compra Asociadas (NUEVO - Estilo 'trazabilidad (1).js' + Flag) ---
        const ocsAsociadasHtml = ocsAsociadasData.length > 0 ? ocsAsociadasData.map(oc => {
            
            // Lógica de Fechas (de trazabilidad (1).js)
            let fechaHtml = `<small class="text-muted">Est: ${oc.fecha_estimada_entrega || 'N/D'}</small>`;
            if (oc.fecha_real_entrega) {
                fechaHtml += `<br><small class="text-muted">Real: ${oc.fecha_real_entrega}</small>`;
            }

            // Lógica de Estado (¡AÑADIDO!)
            let estadoBadgeClass = 'bg-secondary'; // Default
            const estado = (oc.estado || 'N/D').toLowerCase();
            if (estado === 'pendiente' || estado === 'enviada') {
                estadoBadgeClass = 'bg-warning text-dark';
            } else if (estado === 'recibida' || estado === 'completa') {
                estadoBadgeClass = 'bg-success';
            } else if (estado === 'cancelada') {
                estadoBadgeClass = 'bg-danger';
            }

            // Lógica de Flag (¡AÑADIDO!)
            // Asumo que la API devuelve un booleano 'generada_por_op_actual'
            let flagHtml = '';
            if (oc.generada_por_op_actual) { 
                flagHtml = ` <span class="badge bg-primary" title="Generada automáticamente por esta OP"><i class="bi bi-magic"></i> OP</span>`;
            }

            return `
            <div class="card mb-2 shadow-sm">
                <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <a href="/compras/detalle/${oc.id}" class="fw-bold" target="_blank">${oc.codigo_oc || `OC-${oc.id}`}</a>
                            <span class="badge ${estadoBadgeClass} ms-2">${oc.estado || 'N/D'}</span>
                            ${flagHtml}
                        </div>
                        <div class="text-end">
                            ${fechaHtml}
                        </div>
                    </div>
                    <p class="mb-1 small">
                        Proveedor: <a href="/proveedores/${oc.proveedor_id || '#'}/ordenes_compra" target="_blank">${oc.proveedor_nombre || 'N/A'}</a>
                    </p>
                    <ul class="list-unstyled mb-0 small">
                        ${oc.items && oc.items.length > 0 ? 
                            oc.items.map(item => `<li>- ${item.cantidad_solicitada || item.cantidad} x ${item.nombre_insumo || item.nombre}</li>`).join('') : 
                            '<li><small class="text-muted">No hay detalle de items.</small></li>'}
                    </ul>
                </div>
            </div>
            `
        }).join('') : '<p class="text-center text-muted">No hay órdenes de compra asociadas.</p>';


        // --- HTML para Lotes Producidos (Se mantiene estilo 'simple') ---
        const downstreamLotesHtml = lotesProducto.length > 0 ? lotesProducto.map(lote => `
            <tr>
                <td><a href="/lotes-productos/${lote.id}/detalle" target="_blank">${lote.nombre}</a></td>
                <td>${lote.detalle}</td>
            </tr>
        `).join('') : '<tr><td colspan="2" class="text-center text-muted">No se generaron lotes.</td></tr>';
        
        // --- HTML para Pedidos Asociados (Se mantiene estilo 'simple') ---
        const downstreamPedidosHtml = pedidos.length > 0 ? pedidos.map(pedido => `
            <tr>
                <td><a href="/orden-venta/${pedido.id}/detalle" target="_blank">${pedido.nombre}</a></td>
                <td>${pedido.detalle}</td>
                <td class="text-muted">N/A</td>
            </tr>
        `).join('') : '<tr><td colspan="3" class="text-center text-muted">No se encontraron pedidos asociados.</td></tr>';

        // --- 3. Renderizado Final (Plantilla de trazabilidad (1).js) ---
        modalBody.innerHTML = `
            <div class="row">
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-primary text-white"><i class="bi bi-arrow-up-circle-fill"></i> Origen (Upstream)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Insumos Utilizados</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>Insumo</th><th>Lote</th><th>Detalle</th><th>Proveedor</th></tr></thead>
                                    <tbody>${upstreamHtml}</tbody>
                                </table>
                            </div>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Órdenes de Compra Asociadas</h6>
                            ${ocsAsociadasHtml}
                        </div>
                    </div>
                </div>

                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white"><i class="bi bi-arrow-down-circle-fill"></i> Destino (Downstream)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Lotes Producidos</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>N° Lote</th><th>Detalle</th></tr></thead>
                                    <tbody>${downstreamLotesHtml}</tbody>
                                </table>
                            </div>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Pedidos de Cliente Asociados</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-hover">
                                    <thead><tr><th>Pedido</th><th>Detalle</th><th>Fecha Entrega</th></tr></thead>
                                    <tbody>${downstreamPedidosHtml}</tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
});