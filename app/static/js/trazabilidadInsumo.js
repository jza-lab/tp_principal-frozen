google.charts.load('current', { 'packages': ['sankey'] });

document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'lote_insumo';
    const ID_ENTIDAD = window.LOTE_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const sankeyContainer = document.getElementById('sankey_trazabilidad');
    const resumenContenedor = document.getElementById('resumen-trazabilidad-contenedor');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    const accordionButton = document.querySelector('#accordionDiagrama .accordion-button');

    let chart = null;
    let datosCompletosCache = null;

    function mostrarCargando() {
        resumenContenedor.innerHTML = `<div class="card-body text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="mt-2">Cargando resumen...</p></div>`;
        sankeyContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando gráfico...</span></div></div>`;
    }

    function renderizarResumen(resumen) {
        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            resumenContenedor.innerHTML = '<div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div><div class="card-body"><p class="text-muted">No hay datos de resumen para mostrar.</p></div>';
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
            </div>`;
    }

    function renderizarSankey(diagrama) {
        if (!diagrama || !diagrama.edges || !diagrama.edges.length) {
            sankeyContainer.innerHTML = '<div class="alert alert-info">No hay flujos de trazabilidad para mostrar en el diagrama.</div>';
            accordionButton.textContent = 'No hay diagrama disponible';
            accordionButton.classList.add('disabled');
            return;
        }

        accordionButton.textContent = 'Ver Diagrama de Flujo Completo';
        accordionButton.classList.remove('disabled');

        const data = new google.visualization.DataTable();
        data.addColumn('string', 'De');
        data.addColumn('string', 'A');
        data.addColumn('number', 'Cantidad');

        const nodeLabels = {};
        diagrama.nodes.forEach(node => {
            nodeLabels[node.id] = node.label;
        });

        const rows = diagrama.edges.map(edge => [
            nodeLabels[edge.from],
            nodeLabels[edge.to],
            parseFloat(edge.label) || 0
        ]);

        data.addRows(rows);

        const options = {
            width: '100%',
            height: 600, // Aumentado para mejor visualización
            sankey: {
                node: {
                    label: { 
                        fontName: 'Arial',
                        fontSize: 12,
                        color: '#000',
                        bold: false,
                        italic: false
                    },
                    interactivity: true
                },
                link: {
                    colorMode: 'gradient'
                }
            }
        };

        if (chart) {
            chart.clearChart();
        }
        chart = new google.visualization.Sankey(sankeyContainer);
        chart.draw(data, options);
    }

    function cargarDatosTrazabilidad(nivel = 'simple') {
        if (!ID_ENTIDAD) return;

        if (nivel === 'completo' && datosCompletosCache) {
            renderizarResumen(datosCompletosCache.resumen);
            google.charts.setOnLoadCallback(() => renderizarSankey(datosCompletosCache.diagrama));
            return;
        }

        mostrarCargando();
        fetch(`/api/trazabilidad/${TIPO_ENTIDAD}/${ID_ENTIDAD}?nivel=${nivel}`)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                if (result.success && result.data) {
                    if (nivel === 'completo') {
                        datosCompletosCache = result.data;
                    }
                    renderizarResumen(result.data.resumen);
                    google.charts.setOnLoadCallback(() => renderizarSankey(result.data.diagrama));
                } else {
                    resumenContenedor.innerHTML = `<div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div><div class="card-body"><div class="alert alert-warning">${result.error || 'No se pudieron cargar los datos.'}</div></div>`;
                    sankeyContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error al cargar datos:', error);
                resumenContenedor.innerHTML = `<div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div><div class="card-body"><div class="alert alert-danger">Error al conectar con el servidor.</div></div>`;
                sankeyContainer.innerHTML = '';
            });
    }

    if (trazabilidadTab) {
        trazabilidadTab.addEventListener('shown.bs.tab', () => {
            cargarDatosTrazabilidad('simple');
        }, { once: true });
    }

    // Redibujar el diagrama cuando se abre el acordeón para asegurar que se renderice con las dimensiones correctas
    const accordionElement = document.getElementById('accordionDiagrama');
    if (accordionElement) {
        accordionElement.addEventListener('shown.bs.collapse', function () {
            if (chart && datosCompletosCache) {
                // Si ya tenemos los datos y el chart, redibujamos
                google.charts.setOnLoadCallback(() => renderizarSankey(datosCompletosCache.diagrama));
            } else {
                 // Si no (por ejemplo primer carga fue simple, y el diagrama se carga con simple por defecto), 
                 // intentamos redibujar con lo que tengamos en la UI no es fácil.
                 // Pero renderizarSankey ya fue llamado.
                 // Mejor estrategia: si el acordeón se abre, forzamos redibujado si hay datos.
                 // Pero `datosCompletosCache` solo se llena con nivel completo.
                 // El diagrama se carga inicialmente con nivel 'simple'? 
                 // `cargarDatosTrazabilidad('simple')` -> `fetch` -> `renderizarSankey`.
                 // Así que el diagrama ya debería tener datos, pero quizás no en cache.
                 // Vamos a disparar un evento de redibujado window resize que suele arreglar gráficos
                 window.dispatchEvent(new Event('resize'));
            }
        });
    }

    if (nivelSwitch) {
        nivelSwitch.addEventListener('change', function () {
            const nivelSeleccionado = this.checked ? 'completo' : 'simple';
            cargarDatosTrazabilidad(nivelSeleccionado);
        });
    }

    const urls = {
        orden_compra: '/compras/detalle/<id>',
        lote_insumo: '/inventario/lote/<id>',
        orden_produccion: '/ordenes/<id>/detalle',
        lote_producto: '/lotes-productos/<id>/detalle',
        pedido: '/orden-venta/<id>/detalle'
    };
});
