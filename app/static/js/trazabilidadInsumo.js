document.addEventListener('DOMContentLoaded', function () {
    const trazabilidadTab = document.getElementById('trazabilidad-tab');
    if (!trazabilidadTab) return;

    let isDataLoaded = false;
    // HTML-escaping helpers for tooltip safety
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    function escapeAttr(str) {
        return escapeHtml(str).replace(/\"/g, '%22');
    }

    function getEstadoColor(estado) {
        const colorMap = {
            'pendiente': 'warning',
            'en_proceso': 'info',
            'completado': 'success',
            'cancelado': 'danger',
            'rechazado': 'danger',
            'aprobado': 'success',
            'revision': 'warning'
        };
        return colorMap[estado?.toLowerCase()] || 'secondary';
    }

    function mostrarDetallesRiesgo() {
        const modal = new bootstrap.Modal(document.getElementById('modalDetallesRiesgo'));
        modal.show();
    }

    // Implementación propia de debounce
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Función para actualizar dinámicamente el tamaño del diagrama
    function updateChartSize() {
        const container = document.getElementById('sankey_trazabilidad');
        if (container && window.lastChart) {
            const options = window.lastChartOptions;
            options.width = container.clientWidth;
            window.lastChart.draw(window.lastDataTable, options);
        }
    }

    // Agregar listener para redimensionamiento
    window.addEventListener('resize', debounce(updateChartSize, 250));
    
    trazabilidadTab.addEventListener('shown.bs.tab', function () {
        if (!isDataLoaded) {
            loadTrazabilidadData();
            isDataLoaded = true;
        }
    });

    function loadTrazabilidadData() {
        // Detectar tipo de entidad (soporta lote_insumo, lote_producto y orden_produccion)
        let entityType = null;
        let entityId = null;
        if (window.LOTE_ID) {
            entityType = 'lote_insumo';
            entityId = window.LOTE_ID;
        } else if (window.LOTE_PRODUCTO_ID) {
            entityType = 'lote_producto';
            entityId = window.LOTE_PRODUCTO_ID;
        } else if (window.ORDEN_ID || window.ORDEN_PRODUCCION_ID) {
            // Algunos templates pueden exponer ORDEN_ID o ORDEN_PRODUCCION_ID
            entityType = 'orden_produccion';
            entityId = window.ORDEN_ID || window.ORDEN_PRODUCCION_ID;
        }

        if (!entityType || !entityId) {
            console.error('No se encontró identificador de entidad para trazabilidad (esperado window.LOTE_ID, window.LOTE_PRODUCTO_ID o window.ORDEN_ID).');
            return;
        }

        const apiUrl = `/api/trazabilidad/${entityType}/${entityId}`;

        renderSpinner('resumen-trazabilidad');
        renderSpinner('panel-riesgo-proveedor');
        
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                console.log('Datos de trazabilidad recibidos:', JSON.stringify(data, null, 2)); // <-- Log para debugging
                if (data.success) {
                    renderResumen(data.data.resumen);
                    renderPanelRiesgo(data.data.riesgo_proveedor);
                    drawSankeyChart(data.data.diagrama);
                } else {
                    throw new Error(data.error);
                }
            })
            .catch(error => {
                console.error('Error loading traceability data:', error);
                document.getElementById('resumen-trazabilidad').innerHTML = `<div class="alert alert-danger">Error al cargar resumen.</div>`;
                document.getElementById('panel-riesgo-proveedor').innerHTML = `<div class="alert alert-danger">Error al cargar datos de riesgo.</div>`;
            });
    }

    function renderSpinner(elementId) {
        const element = document.getElementById(elementId);
        if(element) element.innerHTML = `<div class="text-center p-3"><div class="spinner-border text-secondary" role="status"></div></div>`;
    }

    function renderResumen(resumen) {
        const container = document.getElementById('resumen-trazabilidad');
        if (!resumen) {
            container.innerHTML = '<p>No se encontró resumen.</p>';
            return;
        }

        // Mostrar campos comunes si existen, y en su defecto usar una representación genérica
        const origen = resumen.origen || resumen.inputs || {};
        const uso = resumen.uso || resumen.outputs || {};

        // Helpers para listas (defensivo: los elementos pueden venir en varias formas)
        const safeListItems = (items, renderItem) => {
            if (!items || items.length === 0) return '<li>N/A</li>';
            return items.map(i => renderItem(i)).join('');
        };

        const opsHtml = safeListItems(uso.ops || uso.ordenes || [], op => {
            const id = op.id || op.order_id || op.orden_id || op.key || '';
            const codigo = op.codigo || op.codigo_op || `OP-${id}`;
            return `<li><a href="/ordenes/${id}/detalle">${escapeHtml(codigo)}</a>${op.cantidad ? ` (usó ${escapeHtml(op.cantidad)})` : ''}</li>`;
        });

        const productosHtml = safeListItems(uso.productos || uso.lotes || uso.outputs || [], p => {
            const id = p.id || p.lote_id || p.producto_id || '';
            const display = p.numero_lote || p.codigo || p.id || p.name || `ID-${id}`;
            return `<li><a href="/lotes-productos/${id}/detalle">${escapeHtml(display)}</a></li>`;
        });

        // Representación general de origen/uso (colapsable si muy grande)
        container.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Origen (Hacia Atrás)</h6>
                    <ul class="list-group list-group-flush">
                        <li class="list-group-item"><strong>Entidad:</strong> ${escapeHtml(origen.tipo || origen.entidad || resumen.tipo || 'N/A')}</li>
                        <li class="list-group-item"><strong>Detalle:</strong> ${escapeHtml(origen.detalle || origen.insumo || origen.nombre || 'N/A')}</li>
                        <li class="list-group-item"><strong>Fuente:</strong> ${origen.orden_compra ? `<a href="/compras/detalle/${origen.orden_compra.id}">${escapeHtml(origen.orden_compra.codigo || origen.orden_compra.id)}</a>` : (escapeHtml(origen.proveedor) || 'N/A')}</li>
                        <li class="list-group-item"><strong>Estado:</strong> ${escapeHtml(origen.estado || origen.calidad || 'N/A')}</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6>Uso (Hacia Adelante)</h6>
                    <strong>Usado en (OPs):</strong>
                    <ul class="list-unstyled">${opsHtml}</ul>
                    <strong>Generó (Productos/Lotes):</strong>
                    <ul class="list-unstyled">${productosHtml}</ul>
                </div>
            </div>`;
    }

    function renderPanelRiesgo(riesgo) {
        const container = document.getElementById('panel-riesgo-proveedor');
        if (!riesgo) {
            container.innerHTML = '<p>No hay datos de riesgo para este proveedor.</p>';
            return;
        }
        const tasaFallos = parseFloat(riesgo.tasa_fallos).toFixed(2);
        const nivelRiesgo = tasaFallos > 10 ? 'alto' : tasaFallos > 5 ? 'medio' : 'bajo';
        const colorRiesgo = {
            'alto': 'danger',
            'medio': 'warning',
            'bajo': 'success'
        }[nivelRiesgo];
        
        container.innerHTML = `
            <div class="card border-${colorRiesgo}">
                <div class="card-body">
                    <h6 class="card-title d-flex justify-content-between align-items-center">
                        <span>Análisis de Riesgo del Proveedor</span>
                        <span class="badge bg-${colorRiesgo}">Riesgo ${nivelRiesgo}</span>
                    </h6>
                    <div class="row align-items-center">
                        <div class="col-md-6">
                            <p class="display-6 mb-0">${tasaFallos}%</p>
                            <p class="text-muted">Tasa de Fallos</p>
                        </div>
                        <div class="col-md-6">
                            <div class="d-flex flex-column">
                                <div class="mb-2">
                                    <small class="text-muted">Lotes Rechazados</small>
                                    <h4 class="mb-0">${riesgo.lotes_rechazados}</h4>
                                </div>
                                <div>
                                    <small class="text-muted">Total Recepciones</small>
                                    <h4 class="mb-0">${riesgo.total_lotes}</h4>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="mt-3">
                        <div class="progress mb-2" style="height: 5px;">
                            <div class="progress-bar bg-${colorRiesgo}" 
                                 role="progressbar" 
                                 style="width: ${tasaFallos}%;" 
                                 aria-valuenow="${tasaFallos}" 
                                 aria-valuemin="0" 
                                 aria-valuemax="100">
                            </div>
                        </div>
                        <div class="d-flex justify-content-between">
                            <a href="#" class="btn btn-sm btn-outline-secondary">
                                <i class="bi bi-file-text me-1"></i>Ver Reportes
                            </a>
                            <a href="#" class="btn btn-sm btn-${colorRiesgo}" onclick="mostrarDetallesRiesgo()">
                                <i class="bi bi-graph-up me-1"></i>Análisis Detallado
                            </a>
                        </div>
                    </div>
                </div>
            </div>`;
    }

    function drawSankeyChart(diagrama) {
        const container = document.getElementById('sankey_trazabilidad');
        if (!diagrama || !diagrama.nodes || diagrama.nodes.length === 0) {
            container.innerHTML = '<div class="alert alert-info text-center p-4">No se encontraron datos para el diagrama.</div>';
            return;
        }
        
        google.charts.load('current', { 'packages': ['sankey'] });
        google.charts.setOnLoadCallback(() => {
            const dataTable = new google.visualization.DataTable();
            dataTable.addColumn('string', 'De');
            dataTable.addColumn('string', 'A');
            dataTable.addColumn('number', 'Cantidad');
            // Columna de tooltip para mostrar la cantidad real al pasar el mouse
            dataTable.addColumn({ type: 'string', role: 'tooltip', p: { html: true } });

            // Mapear ids de nodo a etiquetas legibles (p. ej. código de insumo)
            const idToNode = {};
            diagrama.nodes.forEach(n => { idToNode[n.id] = n; });

            // Construir lista de etiquetas y colores por nodo (en el mismo orden)
            const colorMap = {
                'orden_compra': '#0d6efd', // bootstrap primary
                'lote_insumo': '#6f42c1', // purple
                'orden_produccion': '#198754', // green
                'lote_producto': '#fd7e14', // orange
                'pedido': '#dc3545' // red
            };

            const defaultColor = '#6c757d';
            const nodeLabels = diagrama.nodes.map(n => n.label || n.id);
            const nodeColors = diagrama.nodes.map(n => colorMap[n.group] || defaultColor);

            // Convertir las aristas para usar las etiquetas en lugar de los ids (mejora visual)
            // Procesar los nodos y aristas
            const rawRows = diagrama.edges.map(edge => {
                const fromNode = idToNode[edge.from] || { id: edge.from, label: edge.from, group: '', url: '' };
                const toNode = idToNode[edge.to] || { id: edge.to, label: edge.to, group: '', url: '' };
                const fromLabel = fromNode.label || edge.from;
                const toLabel = toNode.label || edge.to;
                const rawValue = Number(edge.label || edge.value || 1) || 1;
                // Formato HTML para tooltip (más presentable)
                const tooltip = `
                    <div style="max-width:400px;font-family:Roboto, Arial;padding:12px;background:rgba(255,255,255,0.98);border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                        <div style="border-bottom:2px solid ${colorMap[fromNode.group] || defaultColor};margin-bottom:8px;padding-bottom:8px;">
                            <div style="font-size:14px;font-weight:500;color:#1a1a1a;margin-bottom:4px;">
                                <i class="bi bi-arrow-right-circle-fill" style="color:${colorMap[fromNode.group] || defaultColor}"></i>
                                ${escapeHtml(fromLabel)} → ${escapeHtml(toLabel)}
                            </div>
                            <div style="font-size:20px;font-weight:600;color:#333;">
                                ${rawValue} <span style="font-size:12px;color:#666;">unidades</span>
                            </div>
                        </div>
                        <div style="display:grid;grid-template-columns:auto 1fr;gap:8px;margin-bottom:8px;">
                            <div style="font-size:12px;color:#666;">Origen:</div>
                            <div style="font-size:12px;color:#333;font-weight:500;">${escapeHtml(fromNode.group || '')}</div>
                            <div style="font-size:12px;color:#666;">Destino:</div>
                            <div style="font-size:12px;color:#333;font-weight:500;">${escapeHtml(toNode.group || '')}</div>
                            ${fromNode.fecha ? `
                            <div style="font-size:12px;color:#666;">Fecha:</div>
                            <div style="font-size:12px;color:#333;font-weight:500;">${escapeHtml(fromNode.fecha)}</div>
                            ` : ''}
                            ${fromNode.estado || toNode.estado ? `
                            <div style="font-size:12px;color:#666;">Estado:</div>
                            <div style="font-size:12px;color:#333;font-weight:500;">
                                <span class="badge bg-${getEstadoColor(fromNode.estado || toNode.estado)}">${escapeHtml(fromNode.estado || toNode.estado)}</span>
                            </div>
                            ` : ''}
                        </div>
                        ${fromNode.url || toNode.url ? `
                        <div style="margin-top:8px;padding-top:8px;border-top:1px solid #eee;">
                            <a href="${escapeAttr(fromNode.url || toNode.url)}" 
                               style="display:inline-block;padding:4px 12px;background:#0d6efd;color:white;text-decoration:none;border-radius:4px;font-size:12px;">
                                <i class="bi bi-box-arrow-up-right me-1"></i>Ver detalle
                            </a>
                        </div>
                        ` : ''}
                    </div>`;
                return { fromLabel, toLabel, rawValue, tooltip };
            });

            // Calcular los valores para los grosores de las conexiones
            const values = rawRows.map(r => Number(r.rawValue) || 0);
            const maxVal = values.length ? Math.max(...values) : 1;
            
            // Procesar las filas para el diagrama
            const rows = rawRows.map(r => {
                let minVal;
                // Dar más prominencia a las conexiones con órdenes de producción
                if (idToNode[r.fromLabel]?.group === 'orden_produccion' || idToNode[r.toLabel]?.group === 'orden_produccion') {
                    minVal = Math.max(2, maxVal * 0.15); // 15% del máximo para OPs
                }
                // Dar prominencia media a lotes de productos
                else if (idToNode[r.fromLabel]?.group === 'lote_producto' || idToNode[r.toLabel]?.group === 'lote_producto') {
                    minVal = Math.max(1.5, maxVal * 0.1); // 10% del máximo para lotes
                }
                // Mínimo base para otros tipos
                else {
                    minVal = Math.max(1, maxVal * 0.05); // 5% del máximo para otros
                }
                
                return [r.fromLabel, r.toLabel, Math.max(r.rawValue, minVal), r.tooltip];
            });

            // Agregar las filas al dataTable
            dataTable.addRows(rows);

            // Altura dinámica limitada
            // Hacer el gráfico más ancho que alto: limitar la altura y favorecer el ancho
            // Preferir ancho sobre alto: fijar altura pequeña relativa y usar todo el ancho disponible
            // Calcular altura basada en número de nodos, pero dar más espacio
            const chartHeight = Math.max(200, Math.min(400, diagrama.nodes.length * 40));
            
            // Asegurar un ancho mínimo para el contenedor
            container.style.minWidth = '1200px';
            container.style.width = '100%';
            container.style.overflowX = 'auto';
            
            const options = {
                width: Math.max(1200, container.clientWidth || window.innerWidth * 0.95),
                height: chartHeight + 100,
                tooltip: { isHtml: true },
                sankey: {
                    node: {
                        label: { 
                            fontName: 'Roboto, Arial', 
                            fontSize: 14,
                            color: '#212529',
                            bold: true
                        },
                        colors: nodeColors,
                        // Aumentar ancho de nodos significativamente
                        width: 100,
                        padding: 12,
                        // Efecto de resaltado al pasar el mouse y más espacio entre nodos
                        nodePadding: 50,
                        nodeWidth: 60,
                        interactivity: true
                    },
                    link: { 
                        colorMode: 'gradient',
                        fillOpacity: 0.9,
                        // Agregar animación suave
                        animation: {
                            duration: 500,
                            easing: 'out'
                        }
                    }
                }
            };
            
            container.innerHTML = '';
            const chart = new google.visualization.Sankey(container);

            google.visualization.events.addListener(chart, 'select', function() {
                const selection = chart.getSelection();
                if (selection.length > 0) {
                    const selectedItem = selection[0];
                    // Para Sankey, selectedItem.name contiene la etiqueta de nodo
                    const nodeLabel = selectedItem.name || selectedItem.row;
                    if (nodeLabel) {
                        // Buscar nodo por label o por id
                        const node = diagrama.nodes.find(n => n.label === nodeLabel || n.id === nodeLabel || (idToNode[n.id] && idToNode[n.id].label === nodeLabel));
                        if (node && node.url) {
                            window.location.href = node.url;
                        }
                    }
                }
            });

            chart.draw(dataTable, options);
        });
    }

    const btnCrearAlerta = document.getElementById('btn-crear-alerta');
    if(btnCrearAlerta) {
        btnCrearAlerta.addEventListener('click', function() {
            this.disabled = true;
            this.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...`;

            const postData = {
                tipo_entidad: 'lote_insumo',
                id_entidad: window.LOTE_ID
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
                    alert('Error al crear la alerta: ' + (data.error || 'Error desconocido'));
                    this.disabled = false;
                    this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
                alert('Error de red al crear la alerta.');
                this.disabled = false;
                this.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Crear Alerta de Riesgo`;
            });
        });
    }
});
