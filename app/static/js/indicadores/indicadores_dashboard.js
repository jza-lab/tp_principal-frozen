document.addEventListener('DOMContentLoaded', function () {
    const tabElements = document.querySelectorAll('#kpiTab .nav-link');
    const tabContentContainer = document.getElementById('kpiTabContent');
    let loadedTabs = new Set();
    let chartInstances = {}; // Para almacenar instancias de ECharts

    // --- UTILS ---
    function obtenerUrlApi(category) {
        const filterComponent = document.getElementById(`interactive-filter-${category}`);
        if (!filterComponent) {
            return `/reportes/api/indicadores/${category}`; // Sin filtro
        }
        
        const activeButton = filterComponent.querySelector('.filter-pill-group .btn-primary');
        const periodType = activeButton ? activeButton.dataset.period : 'semana';
        let params = '';

        if (periodType === 'semana') {
            const weekValue = filterComponent.querySelector('input[type="week"]').value;
            if(weekValue) params = `semana=${weekValue}`;
        } else if (periodType === 'mes') {
            const monthValue = filterComponent.querySelector('input[type="month"]').value;
            if(monthValue) params = `mes=${monthValue}`;
        } else if (periodType === 'ano') {
            const activeYearButton = filterComponent.querySelector('.year-btn.btn-primary');
            if(activeYearButton) params = `ano=${activeYearButton.dataset.year}`;
        }
        
        return `/reportes/api/indicadores/${category}?${params}`;
    }

    function showLoading(tabPane) {
        tabPane.innerHTML = `
            <div class="loading-placeholder text-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p class="mt-2">Cargando datos...</p>
            </div>`;
    }

    function showError(tabPane, message) {
        // --- MODIFICADO: Añadido console.log para debugging ---
        console.log("Mostrando error en UI:", message); 
        // --- MODIFICADO: Mensaje de error más claro ---
        tabPane.innerHTML = `
            <div class="alert alert-danger text-center p-5" role="alert">
                <strong>Error al cargar:</strong> ${message || 'No se pudieron cargar los datos.'}
            </div>`;
    }
    
    // --- RENDER FUNCTIONS ---

    function createChart(containerId, options, category) {
        const chartDom = document.getElementById(containerId);
        if (!chartDom) return;

        // Limpiar instancia previa si existe
        if (chartInstances[containerId]) {
            chartInstances[containerId].dispose();
        }

        // --- NUEVA LÓGICA: Mostrar mensaje si no hay datos ---
        const hasData = options.series && options.series.some(s => s.data && s.data.length > 0);
        
        if (!hasData) {
            chartDom.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100 text-muted">No hay datos disponibles para el período seleccionado.</div>`;
            return; // No inicializar ECharts
        }
        // --- FIN NUEVA LÓGICA ---

        const chart = echarts.init(chartDom);
        chart.setOption(options);
        chartInstances[containerId] = chart;
    }

    function renderKpiCard(title, value, subtitle, iconClass = 'bi-bar-chart-line') {
        return `
        <div class="col-md-4 mb-4">
            <div class="card text-center h-100">
                <div class="card-header">${title}</div>
                <div class="card-body">
                    <i class="bi ${iconClass} fs-1 text-primary"></i>
                    <h2 class="card-title my-2">${value}</h2>
                    <p class="card-text text-muted">${subtitle}</p>
                </div>
            </div>
        </div>`;
    }

    function renderChartCard(chartId, title, subtitle, tooltip, downloadId, chartHeight = '400px') {
         return `
            <div class="card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="card-title mb-0">${title}</h5>
                        <small class="text-muted">${subtitle}</small>
                    </div>
                    <i class="bi bi-info-circle" data-bs-toggle="tooltip" title="${tooltip}"></i>
                </div>
                <div class="card-body">
                    <div id="${chartId}" style="height: ${chartHeight};"></div>
                    <p id="${chartId}-descripcion" class="mt-2 text-center small"></p>
                </div>
                <div class="card-footer text-end">
                    <button id="${downloadId}" class="btn btn-sm btn-outline-secondary">Descargar</button>
                </div>
            </div>`;
    }
    
    // --- DATA LOADING & RENDERING ---
    
    async function loadTabData(category) {
        const tabPane = document.querySelector(`#${category}`);
        if (!tabPane) return;

        // Previene recargas innecesarias al solo cambiar de pestaña
        if (loadedTabs.has(category)) {
            return;
        }

        showLoading(tabPane);

        try {
            const response = await fetch(obtenerUrlApi(category));
            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.statusText} (Status: ${response.status})`);
            }
            const data = await response.json();

            tabPane.innerHTML = ''; // Limpiar el spinner

            const renderFunctions = {
                'produccion': renderProduccion,
                'calidad': renderCalidad,
                'comercial': renderComercial,
                'financiera': renderFinanciera,
                'inventario': renderInventario,
            };

            if (renderFunctions[category]) {
                await renderFunctions[category](data); // Usar await para funciones asíncronas
            } else {
                showError(tabPane, `No hay una función de renderizado para '${category}'.`);
            }

            loadedTabs.add(category); // Marcar como cargado para evitar recargas

            // Re-inicializar tooltips de Bootstrap después de renderizar
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl)
            });

        } catch (error) {
            console.error(`Error detallado al cargar datos para ${category}:`, error);
            showError(tabPane, error.message);
        }
    }
    
    function renderProduccion(data) {
        const container = document.getElementById('produccion');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('OEE', `${data.oee.valor.toFixed(2)}%`, `Disponibilidad: ${(data.oee.disponibilidad * 100).toFixed(1)}% | Rendimiento: ${(data.oee.rendimiento * 100).toFixed(1)}% | Calidad: ${(data.oee.calidad * 100).toFixed(1)}%`);
        content += renderKpiCard('Cumplimiento del Plan', `${data.cumplimiento_plan.valor.toFixed(2)}%`, `${data.cumplimiento_plan.completadas_a_tiempo} de ${data.cumplimiento_plan.planificadas} órdenes a tiempo`);
        content += '</div>';
        container.innerHTML = content;
    }

    function renderCalidad(data) {
        const container = document.getElementById('calidad');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Rechazo Interno', `${data.tasa_rechazo_interno.valor.toFixed(2)}%`, `${data.tasa_rechazo_interno.rechazadas} de ${data.tasa_rechazo_interno.inspeccionadas} unidades rechazadas`);
        content += renderKpiCard('Reclamos de Clientes', `${data.tasa_reclamos_clientes.valor.toFixed(2)}%`, `${data.tasa_reclamos_clientes.reclamos} reclamos en ${data.tasa_reclamos_clientes.pedidos_entregados} pedidos`);
        content += renderKpiCard('Rechazo de Proveedores', `${data.tasa_rechazo_proveedores.valor.toFixed(2)}%`, `${data.tasa_rechazo_proveedores.rechazados} de ${data.tasa_rechazo_proveedores.recibidos} lotes rechazados`);
        content += '</div>';
        container.innerHTML = content;
    }

    async function renderComercial(data) {
        const container = document.getElementById('comercial');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Cumplimiento de Pedidos', `${data.kpis_comerciales.cumplimiento_pedidos.valor.toFixed(2)}%`, `${data.kpis_comerciales.cumplimiento_pedidos.completados} de ${data.kpis_comerciales.cumplimiento_pedidos.total} pedidos a tiempo`);
        content += renderKpiCard('Valor Promedio Pedido', `$${data.kpis_comerciales.valor_promedio_pedido.valor.toFixed(2)}`, `Basado en ${data.kpis_comerciales.valor_promedio_pedido.num_pedidos} pedidos`);
        content += '</div><div class="row mt-4"><div class="col-lg-6 mb-4">';
        content += renderChartCard('top-productos-chart', 'Top 5 Productos Vendidos', 'Productos más vendidos por cantidad.', 'Suma de cantidades en pedidos completados.', 'download-top-productos');
        content += '</div><div class="col-lg-6 mb-4">';
        content += renderChartCard('top-clientes-chart', 'Top 5 Clientes', 'Clientes con mayor valor de compra.', 'Suma del total de pedidos completados.', 'download-top-clientes');
        content += '</div></div>';
        container.innerHTML = content;

        await renderizarFiltroInteractivo('comercial', 'comercial');

        createChart('top-productos-chart', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'category', data: data.top_productos_vendidos.labels },
            yAxis: { type: 'value' },
            series: [{ data: data.top_productos_vendidos.data, type: 'bar' }]
        });
        
        createChart('top-clientes-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', radius: '50%', data: data.top_clientes.labels.map((name, i) => ({value: data.top_clientes.data[i], name})) }]
        });
    }

    function renderFinanciera(data) {
        const container = document.getElementById('financiera');
        let content = '<div class="row mt-4">';
        // Aquí podrías renderizar KPIs financieros si los hubiera en el futuro.
        // Por ahora, como no hay KPIs numéricos definidos para esta sección,
        // podrías mostrar un mensaje o simplemente dejarlo vacío.
        // Para este caso, mostraremos los KPIs que ya se calculan en el backend
        // aunque no estuvieran visibles antes.
        if (data.kpis_financieros) {
            content += renderKpiCard(data.kpis_financieros.facturacion_total.etiqueta, `$${data.kpis_financieros.facturacion_total.valor.toFixed(2)}`, `Período seleccionado`);
            content += renderKpiCard(data.kpis_financieros.costo_total.etiqueta, `$${data.kpis_financieros.costo_total.valor.toFixed(2)}`, `Costo de Ventas (COGS)`);
            content += renderKpiCard(data.kpis_financieros.beneficio_bruto.etiqueta, `$${data.kpis_financieros.beneficio_bruto.valor.toFixed(2)}`, `Facturación - Costo Total`);
            content += renderKpiCard(data.kpis_financieros.margen_beneficio.etiqueta, `${data.kpis_financieros.margen_beneficio.valor.toFixed(2)}%`, `(Beneficio / Facturación) * 100`);
        }
        content += '</div>';
        container.innerHTML = content;
    }
    
    function renderInventario(data) {
        const container = document.getElementById('inventario');
        let content = '<div class="row mt-4">';
        content += renderKpiCard('Rotación de Inventario', data.kpis_inventario.rotacion_inventario.valor.toFixed(2), `Basado en un COGS de $${data.kpis_inventario.rotacion_inventario.cogs.toFixed(0)} y stock valorizado de $${data.kpis_inventario.rotacion_inventario.inventario_valorizado.toFixed(0)}`);
        content += '</div><div class="row mt-4"><div class="col-lg-6 mb-4">';
        content += renderChartCard('antiguedad-insumos-chart', 'Antigüedad de Stock (Insumos)', 'Valor del inventario por antigüedad.', 'Basado en fecha de ingreso de lotes.', 'download-antiguedad-insumos');
        content += '</div><div class="col-lg-6 mb-4">';
        content += renderChartCard('antiguedad-productos-chart', 'Antigüedad de Stock (Productos)', 'Valor del inventario por antigüedad.', 'Basado en fecha de producción de lotes.', 'download-antiguedad-productos');
        content += '</div></div>';
        container.innerHTML = content;

        createChart('antiguedad-insumos-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', data: data.antiguedad_stock_insumos.labels.map((name, i) => ({value: data.antiguedad_stock_insumos.data[i], name})) }]
        });
        createChart('antiguedad-productos-chart', {
             tooltip: { trigger: 'item' },
             series: [{ type: 'pie', data: data.antiguedad_stock_productos.labels.map((name, i) => ({value: data.antiguedad_stock_productos.data[i], name})) }]
        });
    }

    async function renderizarFiltroInteractivo(containerId, category) {
        // --- 1. Definir HTML y CSS para el nuevo filtro ---
        const style = `
            <style>
                .filter-pill-group .btn {
                    border-radius: 50rem; /* p-pill */
                    margin-right: 0.5rem;
                    font-size: 0.9rem;
                }
                .filter-selector-container {
                    padding: 1rem;
                    border: 1px solid #dee2e6;
                    border-radius: 0.375rem;
                    margin-top: 1rem;
                    transition: all 0.3s ease-in-out;
                    overflow: hidden;
                }
                .filter-selector-content {
                    display: none;
                    opacity: 0;
                    transition: opacity 0.3s ease-in-out;
                }
                .filter-selector-content.active {
                    display: block;
                    opacity: 1;
                }
                .tab-pane.fade-out {
                    opacity: 0;
                    transition: opacity 0.15s ease-out;
                }
                .tab-pane.fade-in {
                    opacity: 1;
                    transition: opacity 0.15s ease-in;
                }
            </style>
        `;

        const filterHtml = `
            <div id="interactive-filter-${category}" class="mb-4">
                <div class="filter-pill-group" role="group">
                    <button type="button" class="btn btn-primary" data-period="semana">Semana</button>
                    <button type="button" class="btn btn-outline-secondary" data-period="mes">Mes</button>
                    <button type="button" class="btn btn-outline-secondary" data-period="ano">Año</button>
                </div>
                <div class="filter-selector-container">
                    <div id="semana-selector-${category}" class="filter-selector-content active">
                        <!-- Contenido del selector de semana irá aquí -->
                        <input type="week" class="form-control">
                    </div>
                    <div id="mes-selector-${category}" class="filter-selector-content">
                        <!-- Contenido del selector de mes irá aquí -->
                        <input type="month" class="form-control">
                    </div>
                    <div id="ano-selector-${category}" class="filter-selector-content">
                        <!-- Contenido del selector de año irá aquí -->
                    </div>
                </div>
            </div>
        `;

        // --- 2. Insertar en el DOM y añadir lógica ---
        const container = document.getElementById(containerId);
        if (container) {
            // Insertar estilos si no existen
            if (!document.head.querySelector('#filter-styles')) {
                const styleSheet = document.createElement('style');
                styleSheet.id = 'filter-styles';
                styleSheet.innerText = style;
                document.head.appendChild(styleSheet);
            }
            container.insertAdjacentHTML('afterbegin', filterHtml);

            // --- 3. Lógica del componente ---
            const filterComponent = document.getElementById(`interactive-filter-${category}`);
            const pillButtons = filterComponent.querySelectorAll('.filter-pill-group .btn');
            const contentDivs = filterComponent.querySelectorAll('.filter-selector-content');

            pillButtons.forEach(button => {
                button.addEventListener('click', (e) => {
                    e.preventDefault(); // Evitar cualquier comportamiento por defecto

                    // Actualizar estilo de botones
                    pillButtons.forEach(btn => {
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-outline-secondary');
                    });
                    button.classList.add('btn-primary');
                    button.classList.remove('btn-outline-secondary');

                    // Mostrar el contenido correcto
                    const period = button.dataset.period;
                    contentDivs.forEach(div => {
                        div.classList.remove('active');
                    });
                    document.getElementById(`${period}-selector-${category}`).classList.add('active');
                    
                    // No recargar aquí, solo al cambiar el valor del input
                });
            });

            // Lógica para poblar selector de año
            const yearSelectorContent = document.getElementById(`ano-selector-${category}`);
            fetch('/reportes/api/indicadores/anos-disponibles')
                .then(res => res.json())
                .then(result => {
                    if (result.success && result.data.length > 0) {
                        const yearButtonsHTML = result.data.map(year => 
                            `<button type="button" class="btn btn-sm btn-outline-primary year-btn" data-year="${year}">${year}</button>`
                        ).join('');
                        yearSelectorContent.innerHTML = `<div class="btn-group">${yearButtonsHTML}</div>`;
                        
                        // Add listeners to new year buttons
                        const yearButtons = yearSelectorContent.querySelectorAll('.year-btn');
                        yearButtons.forEach(btn => {
                            btn.addEventListener('click', (e) => {
                                e.preventDefault();
                                
                                // Manage active state visually by swapping classes
                                yearButtons.forEach(b => {
                                    b.classList.remove('btn-primary');
                                    b.classList.add('btn-outline-primary');
                                });
                                btn.classList.add('btn-primary');
                                btn.classList.remove('btn-outline-primary');

                                // Reload tab data with the new year
                                loadedTabs.delete(category);
                                chartInstances = {};
                                loadTabData(category);
                            });
                        });
                    }
                });

            // Listeners para los inputs de semana y mes
            ['week', 'month'].forEach(type => {
                const input = filterComponent.querySelector(`input[type="${type}"]`);
                input.addEventListener('change', (e) => {
                    e.preventDefault();
                    loadedTabs.delete(category);
                    chartInstances = {};
                    loadTabData(category);
                });
            });
        }
    }

    // --- EVENT LISTENERS ---

    tabElements.forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const category = event.target.dataset.category;
            loadTabData(category);
        });
    });

    // Cargar la primera pestaña activa al inicio
    const initialActiveTab = document.querySelector('#kpiTab .nav-link.active');
    if (initialActiveTab) {
        loadTabData(initialActiveTab.dataset.category);
    }
});