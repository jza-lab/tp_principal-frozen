document.addEventListener('DOMContentLoaded', function () {
    const tabElements = document.querySelectorAll('#kpiTab .nav-link');
    const dashboardState = {}; 
    let loadedTabs = new Set();
    let chartInstances = {}; 

    // --- UTILS ---

    function obtenerUrlApi(category) {
        const state = dashboardState[category] || { period: 'semana', value: '' };
        let params = '';
        if (state.value) params = `${state.period}=${state.value}`;
        return `/reportes/api/indicadores/${category}?${params}`;
    }

    function showLoading(tabPane) {
        tabPane.innerHTML = `
            <div class="loading-placeholder text-center py-5">
                <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
                <p class="mt-2 text-muted small">Calculando indicadores...</p>
            </div>`;
    }

    function showError(tabPane, message) {
        tabPane.innerHTML = `
            <div class="alert alert-danger d-flex align-items-center m-3 p-2 small" role="alert">
                <i class="bi bi-exclamation-triangle-fill flex-shrink-0 me-2"></i>
                <div>${message || 'Error de carga.'}</div>
            </div>`;
    }
    
    // --- RENDER FUNCTIONS (COMPONENTES UI) ---

    function createChart(containerId, options) {
        const chartDom = document.getElementById(containerId);
        if (!chartDom) return;
        if (chartInstances[containerId]) chartInstances[containerId].dispose();

        // Verificación especial para Gauges (que no usan 'series.data' convencional)
        const isGauge = options.series && options.series[0] && options.series[0].type === 'gauge';
        const hasData = isGauge || (options.series && options.series.some(s => s.data && s.data.length > 0));
        
        if (!hasData) {
            chartDom.innerHTML = `<div class="d-flex flex-column justify-content-center align-items-center h-100 text-muted opacity-50 small"><span>Sin datos</span></div>`;
            return;
        }

        const chart = echarts.init(chartDom);
        chart.setOption(options);
        chartInstances[containerId] = chart;
        window.addEventListener('resize', () => chart.resize());
    }

    // TARJETA KPI CON TOOLTIP MEJORADA
    function renderKpiCard(title, value, subtitle, iconClass = 'bi-bar-chart-line', tooltipInfo = null) {
        // Tooltip HTML construction
        const tooltipAttr = tooltipInfo 
            ? `data-bs-toggle="tooltip" data-bs-placement="top" data-bs-html="true" title="${tooltipInfo}"` 
            : '';
        
        const infoIcon = tooltipInfo
            ? `<i class="bi bi-info-circle-fill text-muted ms-2" style="font-size: 0.8rem; cursor: help;" ${tooltipAttr}></i>`
            : '';

        return `
        <div class="col-xl-3 col-md-6 mb-3">
            <div class="card stat-card h-100 border-0 shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <div class="d-flex align-items-center">
                            <h6 class="card-subtitle text-muted text-uppercase fw-bold mb-0" style="font-size: 0.75rem;">${title}</h6>
                            ${infoIcon}
                        </div>
                        <div class="icon-box bg-primary bg-opacity-10 text-primary rounded-circle p-2 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                            <i class="bi ${iconClass}" style="font-size: 1rem;"></i>
                        </div>
                    </div>
                    <h3 class="card-title mb-1 fw-bold text-dark fs-3">${value}</h3>
                    <small class="text-muted" style="font-size: 0.75rem;">${subtitle}</small>
                </div>
            </div>
        </div>`;
    }

    function renderChartCard(chartId, title, subtitle, tooltip, downloadId, chartHeight = '300px') {
         return `
            <div class="card shadow-sm border-0 h-100">
                <div class="card-header bg-white border-bottom-0 pt-3 px-3 d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="fw-bold mb-0 text-dark">${title}</h6>
                        <small class="text-muted">${subtitle}</small>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-link text-muted p-0 no-arrow" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><button class="dropdown-item small" id="${downloadId}"><i class="bi bi-download me-2"></i>Descargar imagen</button></li>
                        </ul>
                    </div>
                </div>
                <div class="card-body px-3 pb-3 pt-0">
                    <div id="${chartId}" style="height: ${chartHeight}; width: 100%;"></div>
                </div>
            </div>`;
    }

    // --- DATA LOADING ---
    
    async function loadTabData(category) {
        const tabPane = document.querySelector(`#${category}`);
        if (!tabPane) return;
        if (loadedTabs.has(category)) return;

        showLoading(tabPane);

        try {
            // Inyectar estilos personalizados
            injectCustomStyles();

            const url = obtenerUrlApi(category);
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Error API: ${response.status}`);
            const data = await response.json();

            tabPane.innerHTML = ''; 

            if (['comercial', 'inventario', 'produccion', 'calidad', 'financiera'].includes(category)) {
                await renderizarFiltroInteractivo(tabPane, category);
            }

            const contentContainer = document.createElement('div');
            contentContainer.id = `${category}-content`;
            tabPane.appendChild(contentContainer);

            const renderFunctions = {
                'produccion': renderProduccion,
                'calidad': renderCalidad,
                'comercial': renderComercial,
                'financiera': renderFinanciera,
                'inventario': renderInventario,
            };

            if (renderFunctions[category]) {
                await renderFunctions[category](data, contentContainer);
            }

            loadedTabs.add(category);
            // Inicializar tooltips de Bootstrap
            [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')).map(el => new bootstrap.Tooltip(el));

        } catch (error) {
            console.error(error);
            showError(tabPane, error.message);
        }
    }
    
    // --- RENDER LOGIC: PRODUCCIÓN (CON GAUGE OEE) ---

    function renderProduccion(data, container) {
        // 1. Fila Superior: Visualización OEE y Cumplimiento
        let content = `
        <div class="row g-3 mb-4">
            <div class="col-lg-5">
                <div class="card shadow-sm border-0 h-100">
                    <div class="card-body position-relative p-2">
                        <h6 class="text-center text-muted fw-bold text-uppercase mt-2 mb-0">OEE Global</h6>
                        <div id="oee-gauge-chart" style="height: 250px;"></div>
                        <div class="text-center position-absolute w-100" style="bottom: 15px;">
                            <span class="badge bg-light text-dark border" data-bs-toggle="tooltip" title="Calculado como Disponibilidad × Rendimiento × Calidad">
                                <i class="bi bi-info-circle me-1"></i> Eficiencia General de los Equipos
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-7">
                <div class="row g-3 h-100 align-content-center">
                    ${renderKpiCard('Disponibilidad', `${(data.oee.disponibilidad * 100).toFixed(1)}%`, 'Tiempo Operativo vs Planificado', 'bi-clock-history', 
                        '<b>Fórmula:</b> (Tiempo Operativo / Tiempo Planificado) <br>Mide las pérdidas por paradas no planificadas o averías.')}
                    
                    ${renderKpiCard('Rendimiento', `${(data.oee.rendimiento * 100).toFixed(1)}%`, 'Velocidad Real vs Teórica', 'bi-speedometer', 
                        '<b>Fórmula:</b> (Tiempo Ganado / Tiempo Operativo) <br>Mide si la máquina está produciendo a su velocidad máxima teórica.')}
                    
                    ${renderKpiCard('Calidad', `${(data.oee.calidad * 100).toFixed(1)}%`, 'Piezas Buenas vs Totales', 'bi-check-circle', 
                        '<b>Fórmula:</b> (Piezas Buenas / Piezas Totales) <br>Porcentaje de producción que cumple con los estándares de calidad (sin defectos).')}
                    
                    ${renderKpiCard('Cumplimiento Plan', `${data.cumplimiento_plan.valor.toFixed(1)}%`, `${data.cumplimiento_plan.completadas_a_tiempo} órdenes a tiempo`, 'bi-calendar-check', 
                        'Porcentaje de Órdenes de Producción que se completaron antes o en la fecha meta prometida.')}
                </div>
            </div>
        </div>
        <div class="row g-3">
            <div class="col-12">
                 ${renderChartCard('gantt-produccion', 'Cronograma de Producción', 'Visualización de órdenes activas', 'Diagrama de Gantt de las próximas 15 órdenes.', 'dl-gantt', '250px')}
            </div>
        </div>
        `;
        
        container.innerHTML = content;

        // --- RENDERIZAR GAUGE OEE ---
        const oeeVal = data.oee.valor.toFixed(1);
        // Colores estándar industria: Rojo < 65, Amarillo < 85, Verde > 85
        const colorPalo = [[0.65, '#dc3545'], [0.85, '#ffc107'], [1, '#198754']];

        createChart('oee-gauge-chart', {
            series: [{
                type: 'gauge',
                startAngle: 180,
                endAngle: 0,
                min: 0,
                max: 100,
                splitNumber: 5,
                radius: '90%',
                itemStyle: { color: '#58D9F9' },
                progress: { show: true, width: 18 },
                pointer: { icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z', length: '12%', width: 10, offsetCenter: [0, '-60%'], itemStyle: { color: 'auto' } },
                axisLine: { lineStyle: { width: 18, color: colorPalo } },
                axisTick: { distance: -18, length: 8, lineStyle: { color: '#fff', width: 2 } },
                splitLine: { distance: -18, length: 30, lineStyle: { color: '#fff', width: 3 } },
                axisLabel: { color: 'auto', distance: 20, fontSize: 12 },
                detail: { valueAnimation: true, formatter: '{value}%', color: 'auto', fontSize: 30, offsetCenter: [0, '20%'] },
                data: [{ value: oeeVal }]
            }]
        });

        // Renderizar Gantt (Placeholder simple para visualización)
        if(data.ordenes_gantt && data.ordenes_gantt.length > 0){
             const opNames = data.ordenes_gantt.map(o => `OP-${o.id_orden_produccion}`);
             const opFechas = data.ordenes_gantt.map(o => {
                 // Simplificado: Duración basada en fecha inicio y fin
                 return [new Date(o.fecha_inicio_planificada).getTime(), new Date(o.fecha_fin_planificada).getTime()];
             });
             // Nota: Un Gantt real en ECharts requiere configuración compleja 'custom'. 
             // Aquí usaremos un bar chart horizontal simple por ahora o texto si es muy complejo.
             createChart('gantt-produccion', {
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                xAxis: { type: 'value', scale: true, axisLabel: { formatter: (val) => new Date(val).toLocaleDateString() } },
                yAxis: { type: 'category', data: opNames },
                series: [{ 
                    type: 'bar', 
                    stack: 'total',
                    itemStyle: { color: 'transparent' },
                    data: data.ordenes_gantt.map(o => new Date(o.fecha_inicio_planificada).getTime()) // Offset transparente
                }, {
                    type: 'bar',
                    stack: 'total',
                    itemStyle: { color: '#3b82f6', borderRadius: 4 },
                    data: data.ordenes_gantt.map(o => new Date(o.fecha_fin_planificada).getTime() - new Date(o.fecha_inicio_planificada).getTime()) // Duración real
                }]
             });
        } else {
            document.getElementById('gantt-produccion').innerHTML = '<div class="text-center pt-5 text-muted">No hay datos de Gantt</div>';
        }
    }

    function renderCalidad(data, container) {
        let content = '<div class="row g-3 mb-3">';
        content += renderKpiCard('Rechazo Interno', `${data.tasa_rechazo_interno.valor.toFixed(2)}%`, `${data.tasa_rechazo_interno.rechazadas} un. descartadas`, 'bi-x-circle',
            'Porcentaje de productos detectados como defectuosos durante el proceso de producción interno, antes de salir de fábrica.');
        
        content += renderKpiCard('Reclamos', `${data.tasa_reclamos_clientes.valor.toFixed(2)}%`, `${data.tasa_reclamos_clientes.reclamos} reclamos activos`, 'bi-emoji-frown',
            'Porcentaje de pedidos entregados que resultaron en un reclamo formal por parte del cliente.');
        
        content += renderKpiCard('Rechazo Prov.', `${data.tasa_rechazo_proveedores.valor.toFixed(2)}%`, `${data.tasa_rechazo_proveedores.rechazados} lotes`, 'bi-truck-flatbed',
            'Porcentaje de lotes de materia prima rechazados en la recepción por no cumplir estándares de calidad.');
        content += '</div>';
        container.innerHTML = content;
    }

    async function renderComercial(data, container) {
        let content = '<div class="row g-3 mb-3">';
        content += renderKpiCard('Cumplimiento', `${data.kpis_comerciales.cumplimiento_pedidos.valor.toFixed(1)}%`, `${data.kpis_comerciales.cumplimiento_pedidos.completados} completados`, 'bi-box-seam',
            'Ratio de pedidos entregados exitosamente sobre el total de pedidos recibidos en el periodo.');
        
        content += renderKpiCard('Ticket Medio', `$${data.kpis_comerciales.valor_promedio_pedido.valor.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`, `${data.kpis_comerciales.valor_promedio_pedido.num_pedidos} pedidos`, 'bi-receipt',
            'Valor monetario promedio de cada venta realizada. (Ingresos Totales / Número de Pedidos).');
        content += '</div><div class="row g-3">';
        
        content += '<div class="col-lg-6">';
        content += renderChartCard('top-productos-chart', 'Top Productos', 'Por cantidad vendida', 'Los productos más populares.', 'download-top-productos');
        content += '</div><div class="col-lg-6">';
        content += renderChartCard('top-clientes-chart', 'Top Clientes', 'Por facturación', 'Los clientes que más ingresos generan.', 'download-top-clientes');
        content += '</div></div>';
        
        container.innerHTML = content;

        createChart('top-productos-chart', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: { type: 'category', data: data.top_productos_vendidos.labels, axisLabel: { interval: 0, rotate: 15, fontSize: 10 } },
            yAxis: { type: 'value' },
            series: [{ data: data.top_productos_vendidos.data, type: 'bar', itemStyle: { color: '#4e73df', borderRadius: [4, 4, 0, 0] }, barWidth: '40%' }]
        });
        
        createChart('top-clientes-chart', {
             tooltip: { trigger: 'item' },
             legend: { bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {fontSize: 10} },
             series: [{ type: 'pie', radius: ['40%', '65%'], center: ['50%', '45%'], itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 }, label: { show: false }, data: data.top_clientes.labels.map((name, i) => ({value: data.top_clientes.data[i], name})) }]
        });
    }

    function renderFinanciera(data, container) {
        let content = '<div class="row g-3 mb-3">';
        if (data.kpis_financieros) {
            content += renderKpiCard('Facturación', `$${data.kpis_financieros.facturacion_total.valor.toLocaleString(undefined, {maximumFractionDigits: 0})}`, `Ingresos`, 'bi-wallet2', 'Total facturado en ventas confirmadas durante el periodo seleccionado.');
            content += renderKpiCard('Costos', `$${data.kpis_financieros.costo_total.valor.toLocaleString(undefined, {maximumFractionDigits: 0})}`, `Directos`, 'bi-cash', 'Estimación de costos directos de producción (MP + MO + GF estimados) asociados a las ventas.');
            content += renderKpiCard('Margen', `${data.kpis_financieros.margen_beneficio.valor.toFixed(1)}%`, `Beneficio`, 'bi-percent', 'Porcentaje de ganancia bruta sobre la facturación. ((Ingresos - Costos) / Ingresos).');
        } else {
            content += '<div class="col-12"><div class="alert alert-light border text-center text-muted small">Sin datos financieros.</div></div>';
        }
        content += '</div>';
        container.innerHTML = content;
    }
    
    function renderInventario(data, container) {
        let content = '<div class="row g-3 mb-3">';
        content += renderKpiCard('Rotación', data.kpis_inventario.rotacion_inventario.valor.toFixed(2), `Vueltas/Año`, 'bi-arrow-repeat', 
            'Número de veces que el inventario se ha renovado en el último año. Una rotación alta indica ventas eficientes.');
        
        // Si tuvieras un KPI de Stock Bajo Mínimo, lo añadirías aquí
        if (data.cobertura_stock) {
             const cobVal = data.cobertura_stock.valor === 'Inf' ? '∞' : data.cobertura_stock.valor;
             content += renderKpiCard('Cobertura', cobVal, `Días estimados`, 'bi-shield-check', 'Días estimados que durará el stock actual basado en el consumo promedio diario.');
        }

        content += '</div><div class="row g-3">';
        content += '<div class="col-lg-6">';
        content += renderChartCard('antiguedad-insumos-chart', 'Stock Insumos', 'Antigüedad lotes', 'Muestra cuánto tiempo llevan los insumos almacenados.', 'download-antiguedad-insumos');
        content += '</div><div class="col-lg-6">';
        content += renderChartCard('antiguedad-productos-chart', 'Stock Productos', 'Antigüedad lotes', 'Muestra cuánto tiempo llevan los productos terminados en almacén.', 'download-antiguedad-productos');
        content += '</div></div>';
        
        container.innerHTML = content;

        const pieOptions = (labels, dataValues) => ({
             tooltip: { trigger: 'item' },
             legend: { bottom: '0%', left: 'center', itemWidth: 10, itemHeight: 10, textStyle: {fontSize: 10} },
             series: [{ type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'], itemStyle: { borderRadius: 3, borderColor: '#fff', borderWidth: 1 }, label: { show: false }, data: labels.map((name, i) => ({value: dataValues[i], name})) }]
        });

        createChart('antiguedad-insumos-chart', pieOptions(data.antiguedad_stock_insumos.labels, data.antiguedad_stock_insumos.data));
        createChart('antiguedad-productos-chart', pieOptions(data.antiguedad_stock_productos.labels, data.antiguedad_stock_productos.data));
    }

    // --- FILTRO INTERACTIVO & ESTILOS ---

    async function renderizarFiltroInteractivo(container, category) {
        // Lógica del filtro (igual que versión anterior)
        if (!dashboardState[category]) dashboardState[category] = { period: 'semana', value: '' };
        const currentState = dashboardState[category];

        let yearOptionsHtml = '';
        if (currentState.period === 'ano') {
            try {
                const res = await fetch('/reportes/api/indicadores/anos-disponibles');
                const json = await res.json();
                if (json.success) {
                    yearOptionsHtml = json.data.map(year => 
                        `<option value="${year}" ${currentState.value == year ? 'selected' : ''}>${year}</option>`
                    ).join('');
                }
            } catch (e) { console.error(e); }
        }

        const toolbar = document.createElement('div');
        toolbar.className = 'compact-toolbar';
        
        const btns = {
            semana: currentState.period === 'semana' ? 'btn-white text-primary border shadow-sm fw-bold' : 'btn-outline-secondary border-0',
            mes: currentState.period === 'mes' ? 'btn-white text-primary border shadow-sm fw-bold' : 'btn-outline-secondary border-0',
            ano: currentState.period === 'ano' ? 'btn-white text-primary border shadow-sm fw-bold' : 'btn-outline-secondary border-0',
        };

        let inputHtml = '';
        if (currentState.period === 'semana') inputHtml = `<input type="week" class="form-control form-control-sm bg-white border" value="${currentState.value}" data-type="semana">`;
        else if (currentState.period === 'mes') inputHtml = `<input type="month" class="form-control form-control-sm bg-white border" value="${currentState.value}" data-type="mes">`;
        else if (currentState.period === 'ano') inputHtml = `<select class="form-select form-select-sm bg-white border" data-type="ano"><option value="">Seleccionar</option>${yearOptionsHtml}</select>`;

        toolbar.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="label-text me-2"><i class="bi bi-funnel-fill text-secondary"></i> Filtrar:</span>
                <div class="bg-white p-1 rounded border d-inline-flex">
                    <button type="button" class="btn btn-sm ${btns.semana} px-3 rounded-2 period-btn" data-period="semana">Semana</button>
                    <button type="button" class="btn btn-sm ${btns.mes} px-3 rounded-2 period-btn" data-period="mes">Mes</button>
                    <button type="button" class="btn btn-sm ${btns.ano} px-3 rounded-2 period-btn" data-period="ano">Año</button>
                </div>
            </div>
            <div class="d-flex align-items-center ms-auto">
                <span class="label-text me-2 text-muted fw-normal small">Período:</span>
                ${inputHtml}
            </div>
        `;

        toolbar.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (dashboardState[category].period !== e.target.dataset.period) {
                    dashboardState[category].period = e.target.dataset.period;
                    dashboardState[category].value = ''; 
                    loadedTabs.delete(category);
                    chartInstances = {};
                    loadTabData(category);
                }
            });
        });
        const inputElement = toolbar.querySelector('input, select');
        if (inputElement) {
            inputElement.addEventListener('change', (e) => {
                if (e.target.value) {
                    dashboardState[category].value = e.target.value;
                    loadedTabs.delete(category);
                    chartInstances = {};
                    loadTabData(category);
                }
            });
        }
        container.appendChild(toolbar);
    }

    function injectCustomStyles() {
        if (document.getElementById('dashboard-custom-styles')) return;
        const style = document.createElement('style');
        style.id = 'dashboard-custom-styles';
        style.innerHTML = `
            /* Pestañas estilo 'Pills' Modernas */
            #kpiTab {
                border-bottom: none;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
            }
            #kpiTab .nav-link {
                border: 1px solid transparent;
                background-color: #f8f9fa;
                color: #6c757d;
                border-radius: 50rem; /* Pill shape */
                padding: 0.5rem 1.25rem;
                font-weight: 500;
                transition: all 0.2s ease-in-out;
            }
            #kpiTab .nav-link:hover {
                background-color: #e9ecef;
                color: #495057;
            }
            #kpiTab .nav-link.active {
                background-color: var(--app-primary, #0d6efd);
                color: #fff;
                box-shadow: 0 2px 4px rgba(13, 110, 253, 0.25);
            }
            
            /* Toolbar Compacta */
            .compact-toolbar {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 0.5rem 1rem;
                margin-bottom: 1.5rem;
                border: 1px solid #e9ecef;
                display: flex;
                align-items: center;
                gap: 1rem;
                flex-wrap: wrap;
            }
            .label-text { font-size: 0.85rem; font-weight: 600; color: #555; }
            
            /* Ajustes de Tarjetas */
            .stat-card { transition: transform 0.2s; }
            .stat-card:hover { transform: translateY(-2px); }
            .tooltip-inner { max-width: 300px; text-align: left; }
        `;
        document.head.appendChild(style);
    }

    // --- INIT ---
    tabElements.forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const category = event.target.dataset.category;
            setTimeout(() => Object.values(chartInstances).forEach(chart => chart.resize()), 150);
            loadTabData(category);
        });
    });

    const initialActiveTab = document.querySelector('#kpiTab .nav-link.active');
    if (initialActiveTab) loadTabData(initialActiveTab.dataset.category);
});