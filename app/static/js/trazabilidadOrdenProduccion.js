document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'orden_produccion';
    const ID_ENTIDAD = window.ORDEN_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const visContainer = document.getElementById('vis_trazabilidad');
    const resumenContenedor = document.getElementById('resumen-trazabilidad-contenedor');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    const accordionButton = document.querySelector('#accordionDiagrama .accordion-button');

    let network = null;
    let datosCompletosCache = null; // Cache para los datos de nivel 'completo'

    // Opciones de configuración para el gráfico Vis.js
    const visOptions = {
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
            font: { align: 'middle' },
            smooth: { type: 'cubicBezier' }
        },
        nodes: {
            shape: 'box',
            margin: 10,
            font: { size: 14, color: '#ffffff' },
            borderWidth: 2
        },
        groups: {
            lote_insumo: { color: { background: '#56B4E9', border: '#4691B9' } },
            orden_compra: { color: { background: '#F0E442', border: '#D4C83A' }, font: { color: '#333333' } },
            orden_produccion: { color: { background: '#E69F00', border: '#B87F00' } },
            lote_producto: { color: { background: '#009E73', border: '#007E5C' } },
            pedido: { color: { background: '#CC79A7', border: '#A36085' } },
            ingreso_manual: { color: { background: '#999999', border: '#7A7A7A' } }
        },
        physics: false
    };
    
    /**
     * Muestra un estado de carga en los contenedores.
     */
    function mostrarCargando() {
        resumenContenedor.innerHTML = `
            <div class="card-body text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p class="mt-2">Cargando resumen...</p>
            </div>`;
        visContainer.innerHTML = `
            <div class="d-flex justify-content-center align-items-center h-100">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando gráfico...</span>
                </div>
            </div>`;
    }

    /**
     * Renderiza el resumen de trazabilidad en el DOM.
     * @param {object} resumen - El objeto de resumen con 'origen' y 'destino'.
     */
    function renderizarResumen(resumen) {
        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            resumenContenedor.innerHTML = '<div class="card mb-4"><div class="card-body"><p class="text-muted">No hay datos de resumen para mostrar.</p></div></div>';
            return;
        }

        const agruparPorTipo = (items) => {
            return items.reduce((acc, item) => {
                if (!acc[item.tipo]) {
                    acc[item.tipo] = [];
                }
                acc[item.tipo].push(item);
                return acc;
            }, {});
        };

        const formatearNombreTipo = (tipo) => {
            const nombres = {
                'orden_compra': 'Órdenes de Compra',
                'lote_insumo': 'Lotes de Insumo',
                'orden_produccion': 'Órdenes de Producción',
                'lote_producto': 'Lotes de Producto',
                'pedido': 'Pedidos de Cliente'
            };
            return nombres[tipo] || tipo.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        };

        const renderizarGrupo = (entidadesAgrupadas) => {
            let html = '';
            for (const tipo in entidadesAgrupadas) {
                html += `<strong class="mt-3 d-block">${formatearNombreTipo(tipo)}:</strong>`;
                html += '<div class="list-container mt-1" style="max-height: 250px; overflow-y: auto; border: 1px solid #eee; padding: 5px; border-radius: 5px;">';
                html += '<ul class="list-group list-group-flush">';
                html += entidadesAgrupadas[tipo].map(item => {
                    let badges = '';
                    if (item.tipo === 'orden_compra') {
                        badges += `<span class="badge bg-warning text-dark me-1">${item.estado || 'N/D'}</span>`;
                        if (item.es_directa) {
                            badges += `<span class="badge bg-info text-dark">Auto-generada</span>`;
                        }
                    }
                    return `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <a href="${urls[item.tipo].replace('<id>', item.id)}" class="fw-bold">${item.nombre}</a>
                                <div class="text-muted small">${item.detalle}</div>
                            </div>
                            <div>${badges}</div>
                        </li>`;
                }).join('');
                html += '</ul>';
                html += '</div>';
            }
            return html;
        };
        
        const origenAgrupado = agruparPorTipo(resumen.origen);
        const destinoAgrupado = agruparPorTipo(resumen.destino);

        const origenHtml = Object.keys(origenAgrupado).length ? renderizarGrupo(origenAgrupado) : '<p class="text-muted">No hay entidades de origen.</p>';
        const destinoHtml = Object.keys(destinoAgrupado).length ? renderizarGrupo(destinoAgrupado) : '<p class="text-muted">No hay entidades de destino.</p>';

        resumenContenedor.innerHTML = `
        <div class="card mb-4">
            <div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-up-circle-fill text-primary me-2"></i>Origen (Hacia Atrás)</h5>
                        ${origenHtml}
                    </div>
                    <div class="col-md-6">
                        <h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino (Hacia Adelante)</h5>
                        ${destinoHtml}
                    </div>
                </div>
            </div>
        </div>`;
    }

    /**
     * Inicializa o actualiza el gráfico de red de Vis.js.
     * @param {object} diagrama - El objeto de diagrama con 'nodes' y 'edges'.
     */
    function renderizarDiagrama(diagrama) {
        if (!diagrama || !diagrama.nodes || !diagrama.nodes.length) {
            visContainer.innerHTML = '<div class="alert alert-info">No hay datos de diagrama para mostrar.</div>';
            // Actualizar texto del acordeón
            accordionButton.textContent = 'No hay diagrama disponible';
            accordionButton.classList.add('disabled');
            return;
        }
        
        // Habilitar y resetear el botón del acordeón
        accordionButton.textContent = 'Ver Diagrama de Red';
        accordionButton.classList.remove('disabled');

        const nodes = new vis.DataSet(diagrama.nodes);
        const edges = new vis.DataSet(diagrama.edges);
        
        if (network) {
            network.setData({ nodes, edges });
        } else {
            network = new vis.Network(visContainer, { nodes, edges }, visOptions);
            network.on("click", function (params) {
                if (params.nodes.length > 0) {
                    const node = nodes.get(params.nodes[0]);
                    if (node.url) {
                        window.location.href = node.url;
                    }
                }
            });
        }
    }

    /**
     * Carga los datos de trazabilidad desde la API unificada.
     * @param {string} nivel - 'simple' o 'completo'.
     */
    function cargarDatosTrazabilidad(nivel = 'simple') {
        if (!ID_ENTIDAD) return;

        // Optimización: si pedimos 'completo' y ya lo tenemos en caché, usarlo.
        if (nivel === 'completo' && datosCompletosCache) {
            renderizarResumen(datosCompletosCache.resumen);
            renderizarDiagrama(datosCompletosCache.diagrama);
            return;
        }

        mostrarCargando();
        fetch(`/api/trazabilidad/${TIPO_ENTIDAD}/${ID_ENTIDAD}?nivel=${nivel}`)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                if (result.success && result.data) {
                    // Si el nivel es 'completo', guardar en caché.
                    if (nivel === 'completo') {
                        datosCompletosCache = result.data;
                    }
                    renderizarResumen(result.data.resumen);
                    renderizarDiagrama(result.data.diagrama);
                } else {
                    resumenContenedor.innerHTML = `<div class="card-body"><div class="alert alert-warning">${result.error || 'No se pudieron cargar los datos.'}</div></div>`;
                    visContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error al cargar datos:', error);
                resumenContenedor.innerHTML = `<div class="card-body"><div class="alert alert-danger">Error al conectar con el servidor.</div></div>`;
                visContainer.innerHTML = '';
            });
    }

    // Evento para cargar los datos cuando la pestaña se muestra por primera vez.
    if (trazabilidadTab) {
        trazabilidadTab.addEventListener('shown.bs.tab', () => {
            cargarDatosTrazabilidad('simple'); // Cargar simple por defecto
        }, { once: true });
    }

    // Evento para el cambio de nivel de trazabilidad.
    if (nivelSwitch) {
        nivelSwitch.addEventListener('change', function () {
            const nivelSeleccionado = this.checked ? 'completo' : 'simple';
            cargarDatosTrazabilidad(nivelSeleccionado);
        });
    }

    // Lógica para el modal de crear alerta (se mantiene igual).
    document.querySelectorAll('.btn-crear-alerta').forEach(button => {
        button.addEventListener('click', function () {
            // ... (lógica del modal existente)
        });
    });

    // Mapeo de URLs para el resumen (ya que el JS no puede usar url_for)
    const urls = {
        orden_compra: '/compras/detalle/<id>',
        lote_insumo: '/inventario/lote/<id>',
        orden_produccion: '/ordenes/<id>/detalle',
        lote_producto: '/lotes-productos/<id>/detalle',
        pedido: '/orden-venta/<id>/detalle'
    };
});
