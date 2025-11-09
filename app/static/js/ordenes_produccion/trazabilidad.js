document.addEventListener('DOMContentLoaded', function() {
    const trazabilidadModal = new bootstrap.Modal(document.getElementById('trazabilidadModal'));
    const modalBody = document.getElementById('trazabilidadModalBody');
    const modalTitle = document.getElementById('trazabilidadModalLabel');

    document.querySelectorAll('.btn-trazabilidad').forEach(button => {
        button.addEventListener('click', function() {
            const opId = this.dataset.opId;
            
            modalTitle.textContent = `Trazabilidad de la Orden de Producción #${opId}`;
            modalBody.innerHTML = `<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Cargando...</span></div><p class="mt-2">Cargando datos...</p></div>`;
            trazabilidadModal.show();

            // Fetch data from the new UNIFIED API with level 'simple'
            fetch(`/api/trazabilidad/orden_produccion/${opId}?nivel=simple`)
                .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
                .then(result => {
                    if (result.success && result.data) {
                        renderTrazabilidad(result.data.resumen, opId);
                    } else {
                        throw new Error(result.error || 'No se pudieron obtener los datos.');
                    }
                })
                .catch(error => {
                    modalBody.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
                });
        });
    });

    function renderTrazabilidad(resumen, opId) {
        const origen = resumen.origen || [];
        const destino = resumen.destino || [];

        const ocs = origen.filter(item => item.tipo === 'orden_compra');
        const insumos = origen.filter(item => item.tipo === 'lote_insumo');
        const lotesProducto = destino.filter(item => item.tipo === 'lote_producto');
        const pedidos = destino.filter(item => item.tipo === 'pedido');
        
        const ocsHtml = ocs.length ? ocs.map(oc => `
            <div class="card mb-2 shadow-sm">
                <div class="card-body p-2">
                    <a href="/compras/detalle/${oc.id}" class="fw-bold" target="_blank">${oc.nombre}</a>
                    <p class="mb-1 small">${oc.detalle}</p>
                </div>
            </div>`).join('') : '<p class="text-center text-muted">No hay Órdenes de Compra asociadas.</p>';

        const insumosHtml = insumos.length ? insumos.map(insumo => `
            <tr>
                <td>${insumo.nombre}</td>
                <td><a href="/inventario/lote/${insumo.id}" target="_blank">Ver Lote</a></td>
                <td>${insumo.detalle}</td>
            </tr>`).join('') : '<tr><td colspan="3" class="text-center text-muted">No se utilizaron insumos.</td></tr>';

        const lotesHtml = lotesProducto.length ? lotesProducto.map(lote => `
            <tr>
                <td><a href="/lotes-productos/${lote.id}/detalle" target="_blank">${lote.nombre}</a></td>
                <td>${lote.detalle}</td>
            </tr>`).join('') : '<tr><td colspan="2" class="text-center text-muted">No se generaron lotes.</td></tr>';
        
        const pedidosHtml = pedidos.length ? pedidos.map(pedido => `
            <tr>
                <td><a href="/orden-venta/${pedido.id}/detalle" target="_blank">${pedido.nombre}</a></td>
                <td>${pedido.detalle}</td>
            </tr>`).join('') : '<tr><td colspan="2" class="text-center text-muted">No hay pedidos asociados.</td></tr>';

        modalBody.innerHTML = `
            <div class="row">
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-primary text-white"><i class="bi bi-arrow-up-circle-fill"></i> Origen (Hacia Atrás)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Insumos Utilizados</h6>
                            <table class="table table-sm"><tbody>${insumosHtml}</tbody></table>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Órdenes de Compra</h6>
                            ${ocsHtml}
                        </div>
                    </div>
                </div>
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white"><i class="bi bi-arrow-down-circle-fill"></i> Destino (Hacia Adelante)</div>
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Lotes Producidos</h6>
                            <table class="table table-sm"><tbody>${lotesHtml}</tbody></table>
                            <hr>
                            <h6 class="card-subtitle mb-2 text-muted">Pedidos Asociados</h6>
                            <table class="table table-sm"><tbody>${pedidosHtml}</tbody></table>
                        </div>
                    </div>
                </div>
            </div>`;
    }
});
