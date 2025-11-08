document.addEventListener('DOMContentLoaded', function () {
    const trazabilidadTab = document.getElementById('trazabilidad-tab');
    if (!trazabilidadTab) return;

    let isDataLoaded = false;

    trazabilidadTab.addEventListener('shown.bs.tab', function () {
        if (!isDataLoaded) {
            loadTrazabilidadData();
            isDataLoaded = true;
        }
    });

    function loadTrazabilidadData() {
        const ordenId = window.ORDEN_ID || window.ORDEN_PRODUCCION_ID;
        if (!ordenId) {
            console.error("ORDEN_ID not defined.");
            return;
        }
        const apiUrl = `/api/trazabilidad/orden_produccion/${ordenId}`;

        renderSpinner('resumen-trazabilidad');

        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    renderResumen(data.data.resumen);
                    drawVisNetwork(data.data.diagrama);
                } else {
                    throw new Error(data.error);
                }
            })
            .catch(error => {
                console.error('Error loading traceability data:', error);
                document.getElementById('resumen-trazabilidad').innerHTML = `<div class="alert alert-danger">Error al cargar datos.</div>`;
            });
    }

    function renderSpinner(elementId) {
        const element = document.getElementById(elementId);
        if (element) element.innerHTML = `<div class="text-center p-3"><div class="spinner-border text-secondary" role="status"></div></div>`;
    }

    function renderResumen(data) {
        const container = document.getElementById('resumen-trazabilidad');
        if (!container) return;

        // Adaptador para la estructura de datos que viene de /api/trazabilidad
        const resumen = data.resumen || {};
        const opData = resumen.origen ? resumen.origen.op : {};
        const upstreamData = resumen.origen ? { insumos: resumen.origen.insumos } : { insumos: [] };
        const downstreamData = resumen.destino ? { lotes_producidos: resumen.destino.lotes, pedidos: resumen.destino.pedidos } : { lotes_producidos: [], pedidos: [] };
        const ocsAsociadasData = resumen.ordenes_compra_asociadas || [];

        // --- HTML para Insumos Utilizados ---
        const upstreamHtml = upstreamData.insumos.length > 0 ? upstreamData.insumos.map(insumo => `
            <tr>
                <td>${insumo.nombre_insumo || insumo.nombre}</td>
                <td><a href="/inventario/lote/${insumo.id}" target="_blank">Lote #${insumo.id}</a></td>
                <td>${insumo.cantidad}</td>
            </tr>
        `).join('') : '<tr><td colspan="3" class="text-center text-muted">No se consumieron insumos de lotes específicos.</td></tr>';

        // --- HTML para Órdenes de Compra Pendientes ---
        const ocsAsociadasHtml = ocsAsociadasData.length > 0 ? ocsAsociadasData.map(oc => `
            <div class="card mb-2 shadow-sm">
                <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <a href="/compras/detalle/${oc.id}" class="fw-bold" target="_blank">${oc.codigo_oc}</a>
                            <span class="badge bg-info text-dark ms-2">${oc.estado}</span>
                        </div>
                        <small class="text-muted">Entrega: ${oc.fecha_estimada_entrega || 'N/D'}</small>
                    </div>
                    <p class="mb-1 small">
                        Proveedor: <a href="/proveedores/${oc.proveedor_id}/ordenes_compra" target="_blank">${oc.proveedor_nombre}</a>
                    </p>
                    <ul class="list-unstyled mb-0 small">
                        ${oc.items.map(item => `<li>- ${item.cantidad_solicitada} x ${item.nombre_insumo}</li>`).join('')}
                    </ul>
                </div>
            </div>
        `).join('') : '<p class="text-center text-muted">No hay órdenes de compra asociadas.</p>';

        // --- HTML para Lotes Producidos ---
        const downstreamLotesHtml = downstreamData.lotes_producidos.length > 0 ? downstreamData.lotes_producidos.map(lote => `
            <tr>
                <td><a href="/lotes-productos/${lote.id}/detalle" target="_blank">${lote.codigo}</a></td>
                <td>${lote.cantidad}</td>
            </tr>
        `).join('') : '<tr><td colspan="2" class="text-center text-muted">No se generaron lotes.</td></tr>';

        // --- HTML para Pedidos Asociados ---
        const downstreamPedidosHtml = downstreamData.pedidos.length > 0 ? downstreamData.pedidos.map(pedido => `
            <tr>
                <td><a href="/orden-venta/${pedido.id}/detalle" target="_blank">PED-${pedido.id}</a></td>
                <td>${pedido.cantidad}</td>
                <td>${pedido.lote_producto_id ? `<a href="/lotes-productos/${pedido.lote_producto_id}/detalle">Lote #${pedido.lote_producto_id}</a>` : 'N/A'}</td>
            </tr>
        `).join('') : '<tr><td colspan="3" class="text-center text-muted">No se encontraron pedidos asociados.</td></tr>';

        // --- Renderizado Final ---
        container.innerHTML = `
            <div class="row">
                <!-- Upstream -->
                <div class="col-12 mb-3">
                    <h5 class="text-primary"><i class="bi bi-arrow-up-circle-fill"></i> Origen (Upstream)</h5>
                    <h6 class="card-subtitle mt-3 mb-2 text-muted">Insumos Utilizados</h6>
                    <div class="table-responsive">
                        <table class="table table-sm table-hover">
                            <thead><tr><th>Insumo</th><th>Lote</th><th>Cantidad</th></tr></thead>
                            <tbody>${upstreamHtml}</tbody>
                        </table>
                    </div>
                    <hr>
                    <h6 class="card-subtitle mb-2 text-muted">Órdenes de Compra Asociadas</h6>
                    ${ocsAsociadasHtml}
                </div>

                <!-- Downstream -->
                <div class="col-12">
                    <h5 class="text-success"><i class="bi bi-arrow-down-circle-fill"></i> Destino (Downstream)</h5>
                    <h6 class="card-subtitle mt-3 mb-2 text-muted">Lotes de Producto Generados</h6>
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
                            <thead><tr><th>Pedido</th><th>Cantidad</th><th>Desde Lote</th></tr></thead>
                            <tbody>${downstreamPedidosHtml}</tbody>
                        </table>
                    </div>
                </div>
            </div>`;
    }

    function drawVisNetwork(diagrama) {
        const container = document.getElementById('vis_trazabilidad');
        if (!diagrama || !diagrama.nodes || diagrama.nodes.length === 0) {
            container.innerHTML = '<div class="alert alert-info text-center p-4">No se encontraron datos para el diagrama de red.</div>';
            return;
        }

        const nodes = new vis.DataSet(diagrama.nodes);
        const edges = new vis.DataSet(diagrama.edges);

        const data = { nodes: nodes, edges: edges };
        const options = {
            layout: {
                hierarchical: {
                    direction: "LR",
                    sortMethod: "directed",
                    levelSeparation: 300,
                    nodeSpacing: 200
                }
            },
            edges: {
                arrows: 'to',
                font: {
                    align: 'middle'
                },
                smooth: {
                    type: 'cubicBezier'
                }
            },
            nodes: {
                shape: 'box',
                margin: 10,
                font: {
                    size: 14,
                    color: '#ffffff'
                },
                borderWidth: 2
            },
            groups: {
                lote_insumo: {
                    color: {
                        background: '#56B4E9',
                        border: '#4691B9'
                    }
                },
                orden_compra: {
                    color: {
                        background: '#F0E442',
                        border: '#D4C83A'
                    },
                    font: {
                        color: '#333333'
                    }
                },
                orden_produccion: {
                    color: {
                        background: '#E69F00',
                        border: '#B87F00'
                    }
                },
                lote_producto: {
                    color: {
                        background: '#009E73',
                        border: '#007E5C'
                    }
                },
                pedido: {
                    color: {
                        background: '#CC79A7',
                        border: '#A36085'
                    }
                }
            },
            physics: false,
            interaction: {
                hover: true
            }
        };

        container.innerHTML = '';
        const network = new vis.Network(container, data, options);

        network.on("click", function (params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                if (node && node.url) {
                    window.location.href = node.url;
                }
            }
        });
    }

    const btnCrearAlerta = document.getElementById('btn-crear-alerta');
    if (btnCrearAlerta) {
        btnCrearAlerta.addEventListener('click', function () {
            this.disabled = true;
            this.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...`;

            const postData = {
                tipo_entidad: 'orden_produccion',
                id_entidad: window.ORDEN_ID || window.ORDEN_PRODUCCION_ID
            };

            fetch('/admin/riesgos/crear-alerta', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(postData)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        showNotificationModal('Error', 'Error al crear la alerta: ' + (data.error || 'Error desconocido'));
                        this.disabled = false;
                        this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
                    }
                })
                .catch(error => {
                    console.error('Error en fetch:', error);
                    showNotificationModal('Error de red', 'Error de red al crear la alerta.');
                    this.disabled = false;
                    this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
                });
        });
    }
});
