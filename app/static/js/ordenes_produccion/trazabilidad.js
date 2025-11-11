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

        const gruposOrigen = origen.reduce((acc, item) => {
            if (!acc[item.tipo]) acc[item.tipo] = [];
            acc[item.tipo].push(item);
            return acc;
        }, {});

        const gruposDestino = destino.reduce((acc, item) => {
            if (!acc[item.tipo]) acc[item.tipo] = [];
            acc[item.tipo].push(item);
            return acc;
        }, {});

        const renderizarGrupo = (titulo, items, tipoEntidad) => {
            if (!items || items.length === 0) {
                return `
                    <h6 class="card-subtitle mb-2 text-muted">${titulo}</h6>
                    <p class="text-center text-muted small fst-italic">No hay ${titulo.toLowerCase()} asociados.</p>
                `;
            }

            const itemsHtml = items.map(item => {
                let url;
                switch(tipoEntidad) {
                    case 'orden_compra': url = `/compras/detalle/${item.id}`; break;
                    case 'lote_insumo': url = `/inventario/lote/${item.id}`; break;
                    case 'lote_producto': url = `/lotes-productos/${item.id}/detalle`; break;
                    case 'pedido': url = `/orden-venta/${item.id}/detalle`; break;
                    default: url = '#';
                }

                if (tipoEntidad === 'orden_compra') {
                    const estadoBadge = item.estado ? `<span class="badge bg-warning text-dark ms-2">${item.estado}</span>` : '';
                    const origenBadge = item.es_directa ? `<span class="badge bg-info text-dark ms-2">Auto-generada</span>` : '';
                    return `
                        <div class="card mb-2 shadow-sm">
                            <div class="card-body p-2">
                                <div>
                                    <a href="${url}" class="fw-bold" target="_blank">${item.nombre || 'N/A'}</a>
                                    ${estadoBadge}
                                    ${origenBadge}
                                </div>
                                <p class="mb-1 small text-muted">${item.detalle || ''}</p>
                            </div>
                        </div>
                    `;
                }
                
                return `
                    <div class="card mb-2 shadow-sm">
                        <div class="card-body p-2">
                             <a href="${url}" class="fw-bold" target="_blank">${item.nombre || 'N/A'}</a>
                            <p class="mb-1 small text-muted">${item.detalle || ''}</p>
                        </div>
                    </div>
                `;
            }).join('');

            return `
                <h6 class="card-subtitle mb-2 text-muted">${titulo}</h6>
                ${itemsHtml}
            `;
        };

        const origenHtml = `
            ${renderizarGrupo('Lotes de Insumo', gruposOrigen.lote_insumo, 'lote_insumo')}
            <hr class="my-3">
            ${renderizarGrupo('Órdenes de Compra', gruposOrigen.orden_compra, 'orden_compra')}
        `;
        
        const destinoHtml = `
             ${renderizarGrupo('Lotes de Producto', gruposDestino.lote_producto, 'lote_producto')}
             <hr class="my-3">
             ${renderizarGrupo('Pedidos de Cliente', gruposDestino.pedido, 'pedido')}
        `;

        modalBody.innerHTML = `
            <div class="row">
                <div class="col-lg-6 mb-4 mb-lg-0">
                    <div class="card h-100">
                        <div class="card-header bg-primary text-white"><i class="bi bi-arrow-up-circle-fill me-2"></i> Origen (Hacia Atrás)</div>
                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                            ${origenHtml}
                        </div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white"><i class="bi bi-arrow-down-circle-fill me-2"></i> Destino (Hacia Adelante)</div>
                         <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                            ${destinoHtml}
                        </div>
                    </div>
                </div>
            </div>`;
    }
});
