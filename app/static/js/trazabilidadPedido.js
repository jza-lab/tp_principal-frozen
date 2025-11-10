document.addEventListener('DOMContentLoaded', function () {
    const TIPO_ENTIDAD = 'pedido';
    const ID_ENTIDAD = window.PEDIDO_ID;

    // Elementos del DOM
    const trazabilidadTab = document.querySelector('#trazabilidad-tab');
    const visContainer = document.getElementById('vis_trazabilidad');
    const resumenContenedor = document.getElementById('resumen-trazabilidad-contenedor');
    const nivelSwitch = document.getElementById('trazabilidad-nivel-switch');
    const accordionButton = document.querySelector('#accordionDiagrama .accordion-button');

    let network = null;
    let datosCompletosCache = null;

    const visOptions = {
        layout: { hierarchical: { direction: "LR", sortMethod: "directed", levelSeparation: 300, nodeSpacing: 200 } },
        edges: { arrows: 'to', font: { align: 'middle' }, smooth: { type: 'cubicBezier' } },
        nodes: { shape: 'box', margin: 10, font: { size: 14, color: '#ffffff' }, borderWidth: 2 },
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

    function mostrarCargando() {
        resumenContenedor.innerHTML = `<div class="card mb-4"><div class="card-body text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Cargando...</p></div></div>`;
        visContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary"></div></div>`;
    }

    function renderizarResumen(resumen) {
        if (!resumen || (!resumen.origen.length && !resumen.destino.length)) {
            resumenContenedor.innerHTML = '<div class="card mb-4"><div class="card-body"><p class="text-muted">No hay datos de resumen.</p></div></div>';
            return;
        }

        const agruparEntidades = (lista, titulo, subtitulos) => {
            let html = `<h5 class="mb-3 border-bottom pb-2">${titulo}</h5>`;
            
            for (const [tipo, subtitulo] of Object.entries(subtitulos)) {
                const entidades = lista.filter(item => item.tipo === tipo);
                html += `<strong>${subtitulo}:</strong>`;
                const listaHtml = entidades.length ? entidades.map(item => `
                    <li class="list-group-item">
                        <a href="${(urls[item.tipo] || '#').replace('<id>', item.id)}" class="fw-bold">${item.nombre}</a>
                        <div class="text-muted small">${item.detalle}</div>
                    </li>`).join('') : '<li class="list-group-item text-muted">N/A</li>';
                
                html += `<div class="list-container mt-1 mb-3" style="max-height: 150px; overflow-y: auto; border: 1px solid #eee; padding: 5px; border-radius: 5px;">
                            <ul class="list-group list-group-flush">${listaHtml}</ul>
                         </div>`;
            }
            return html;
        };

        const subtitulosOrigen = {
            'lote_producto': 'Lotes de Producto',
            'orden_produccion': 'Órdenes de Producción',
            'lote_insumo': 'Lotes de Insumo',
            'orden_compra': 'Órdenes de Compra'
        };

        const origenHtml = agruparEntidades(resumen.origen, '<i class="bi bi-arrow-up-circle-fill text-primary me-2"></i>Origen (Hacia Atrás)', subtitulosOrigen);
        
        // Para un pedido, el destino está vacío o es él mismo, por lo que no se renderiza.

        resumenContenedor.innerHTML = `
        <div class="card mb-4">
            <div class="card-header"><i class="bi bi-list-ul me-1"></i> Resumen de Trazabilidad</div>
            <div class="card-body">
                ${origenHtml}
            </div>
        </div>`;
    }


    function renderizarDiagrama(diagrama) {
        if (!diagrama || !diagrama.nodes || !diagrama.nodes.length) {
            visContainer.innerHTML = '<div class="alert alert-info">No hay diagrama.</div>';
            accordionButton.textContent = 'No hay diagrama disponible';
            accordionButton.classList.add('disabled');
            return;
        }
        
        accordionButton.innerHTML = '<i class="bi bi-diagram-3 me-2"></i> Ver Diagrama de Red Completo';
        accordionButton.classList.remove('disabled');

        const nodes = new vis.DataSet(diagrama.nodes);
        const edges = new vis.DataSet(diagrama.edges);
        
        if (network) {
            network.setData({ nodes, edges });
        } else {
            network = new vis.Network(visContainer, { nodes, edges }, visOptions);
            network.on("click", params => {
                if (params.nodes.length > 0) {
                    const node = nodes.get(params.nodes[0]);
                    if (node.url) window.location.href = node.url;
                }
            });
        }
    }

    function cargarDatosTrazabilidad(nivel = 'simple') {
        if (!ID_ENTIDAD) return;

        if (nivel === 'completo' && datosCompletosCache) {
            renderizarResumen(datosCompletosCache.resumen);
            renderizarDiagrama(datosCompletosCache.diagrama);
            return;
        }

        mostrarCargando();
        fetch(`/api/trazabilidad/${TIPO_ENTIDAD}/${ID_ENTIDAD}?nivel=${nivel}`)
            .then(response => response.ok ? response.json() : Promise.reject('Error'))
            .then(result => {
                if (result.success && result.data) {
                    if (nivel === 'completo') datosCompletosCache = result.data;
                    renderizarResumen(result.data.resumen);
                    renderizarDiagrama(result.data.diagrama);
                } else {
                    resumenContenedor.innerHTML = `<div class="card mb-4"><div class="card-body"><div class="alert alert-warning">${result.error || 'Error.'}</div></div></div>`;
                    visContainer.innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resumenContenedor.innerHTML = `<div class="card mb-4"><div class="card-body"><div class="alert alert-danger">Error de conexión.</div></div></div>`;
                visContainer.innerHTML = '';
            });
    }

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
