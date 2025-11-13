google.charts.load('current', { 'packages': ['sankey'] });

document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'orden_compra';
    const ID_ENTIDAD = window.ORDEN_COMPRA_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const sankeyContainer = document.getElementById('sankey_trazabilidad');
    const resumenOrigenContenedor = document.getElementById('resumen-trazabilidad-origen');
    const resumenDestinoContenedor = document.getElementById('resumen-trazabilidad-destino');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    
    let chart = null;
    let datosCompletosCache = null;

    // --- Funciones auxiliares ---
    function wrapLabel(label, maxWidth = 20) {
        if (label.length <= maxWidth) return label;
        
        let wrappedLabel = '';
        let currentLine = '';
        const words = label.split(' ');

        words.forEach(word => {
            if ((currentLine + word).length > maxWidth) {
                wrappedLabel += currentLine.trim() + '\n';
                currentLine = '';
            }
            currentLine += word + ' ';
        });
        wrappedLabel += currentLine.trim();
        return wrappedLabel;
    }
    function agruparPorTipo(items) {
        return items.reduce((acc, item) => {
            (acc[item.tipo] = acc[item.tipo] || []).push(item);
            return acc;
        }, {});
    }

    function formatearNombreTipo(tipo) {
        const nombres = {
            'orden_compra': 'Órdenes de Compra',
            'lote_insumo': 'Lotes de Insumo',
            'orden_produccion': 'Órdenes de Producción',
            'lote_producto': 'Lotes de Producto',
            'pedido': 'Pedidos de Cliente'
        };
        return nombres[tipo] || tipo.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    // --- Funciones de renderizado ---
    function mostrarCargando() {
        if (resumenDestinoContenedor) {
            resumenDestinoContenedor.innerHTML = `<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="mt-2">Cargando resumen...</p></div>`;
        }
        if(resumenOrigenContenedor) resumenOrigenContenedor.innerHTML = '';
        if (sankeyContainer) {
            sankeyContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div><p class="ms-2">Cargando diagrama...</p></div>`;
        }
    }

    function renderizarResumen(resumen) {
        if (!resumenDestinoContenedor || !resumenOrigenContenedor) return;

        resumenOrigenContenedor.innerHTML = ''; // Para OC, el origen no se muestra
        resumenDestinoContenedor.innerHTML = '';

        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            resumenDestinoContenedor.innerHTML = '<p class="text-muted">No hay datos de resumen para mostrar.</p>';
            return;
        }
        
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

        if (resumen.destino.length > 0) {
            const destinoAgrupado = agruparPorTipo(resumen.destino);
            let destinoHtml = '<h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino / Hacia adelante</h5>';
            destinoHtml += renderizarGrupo(destinoAgrupado);
            resumenDestinoContenedor.innerHTML = destinoHtml;
        } else {
            resumenDestinoContenedor.innerHTML = `
                <h5 class="mb-3 border-bottom pb-2"><i class="bi bi-arrow-down-circle-fill text-success me-2"></i>Destino / Hacia adelante</h5>
                <p class="text-muted">No hay entidades posteriores en la trazabilidad.</p>`;
        }
    }

    function renderizarSankey(diagrama) {
        if (!sankeyContainer) return;

        if (!diagrama || !diagrama.edges || !diagrama.edges.length) {
            sankeyContainer.innerHTML = '<div class="alert alert-info m-3">No hay flujos de trazabilidad para mostrar en el diagrama.</div>';
            return;
        }

        const data = new google.visualization.DataTable();
        data.addColumn('string', 'De');
        data.addColumn('string', 'A');
        data.addColumn('number', 'Cantidad');

        const nodeLabels = {};
        diagrama.nodes.forEach(node => {
            nodeLabels[node.id] = wrapLabel(node.label); // Aplicar envoltura de texto
        });

        const rows = diagrama.edges.map(edge => [
            nodeLabels[edge.from],
            nodeLabels[edge.to],
            parseFloat(edge.label) || 0
        ]);

        data.addRows(rows);
        const options = { width: '100%', height: '100%', sankey: { node: { label: { fontSize: 10 } }, link: { colorMode: 'gradient' } } };
        
        if (chart) chart.clearChart();
        chart = new google.visualization.Sankey(sankeyContainer);
        chart.draw(data, options);
    }

    // --- Lógica de Carga ---
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
                    if (nivel === 'completo') datosCompletosCache = result.data;
                    renderizarResumen(result.data.resumen);
                    google.charts.setOnLoadCallback(() => renderizarSankey(result.data.diagrama));
                } else {
                    const errorMsg = result.error || 'No se pudieron cargar los datos.';
                    if (resumenDestinoContenedor) resumenDestinoContenedor.innerHTML = `<div class="alert alert-warning">${errorMsg}</div>`;
                    if (sankeyContainer) sankeyContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                if (resumenDestinoContenedor) resumenDestinoContenedor.innerHTML = `<div class="alert alert-danger">Error de conexión al cargar el resumen.</div>`;
                if (sankeyContainer) sankeyContainer.innerHTML = `<div class="alert alert-danger m-3">Error de conexión al cargar el diagrama.</div>`;
            });
    }

    // --- Event Listeners ---
    if (trazabilidadTab) {
        trazabilidadTab.addEventListener('shown.bs.tab', () => cargarDatosTrazabilidad('simple'), { once: true });
    }

    if (nivelSwitch) {
        nivelSwitch.addEventListener('change', function () {
            cargarDatosTrazabilidad(this.checked ? 'completo' : 'simple');
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
