const inventarioColors = ['#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC', '#91CC75', '#EE6666', '#999999'];

// --- HELPERS ---

function formatCurrency(value) {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value);
}

function createTopNSelector(id, currentValue, onChangeCallback) {
    const select = document.createElement('select');
    select.className = 'form-select form-select-sm d-inline-block w-auto ms-2 border-0 bg-light fw-bold text-primary';
    select.style.cursor = 'pointer';
    
    [5, 10, 15, 20].forEach(n => {
        const option = document.createElement('option');
        option.value = n;
        option.text = `Top ${n}`;
        if (parseInt(currentValue) === n) option.selected = true;
        select.appendChild(option);
    });

    select.addEventListener('change', (e) => onChangeCallback(e.target.value));
    return select;
}

// --- MAIN RENDER FUNCTION ---

window.renderInventario = function(data, container, utils) {
    const { renderKpiCard, createChart, createSmartCardHTML } = utils || window;
    const topN = data.meta?.top_n || 5;

    container.innerHTML = ''; // Clear container

    // Helper to check valid data
    const hasData = (dataset) => dataset && dataset.data && dataset.data.some(v => v > 0);

    // Helper to get insight safely
    const getInsight = (chartName) => data[`${chartName}_chart`] ? data[`${chartName}_chart`].insight : (data[chartName] && data[chartName].insight ? data[chartName].insight : 'Sin análisis disponible.');

    // --- SECCIÓN: INSUMOS ---
    
    const sectionInsumos = document.createElement('div');
    sectionInsumos.className = 'mb-5';
    sectionInsumos.innerHTML = `<h5 class="mb-4 text-primary border-bottom pb-2"><i class="bi bi-box-seam me-2"></i>Gestión de Insumos</h5>`;
    container.appendChild(sectionInsumos);

    // 1. KPIs Insumos
    let kpisInsumos = '<div class="row g-3 mb-4">';
    kpisInsumos += renderKpiCard(
        'Insumos Críticos', 
        data.kpis_inventario.insumos_criticos, 
        'Bajo stock mín.', 
        'bi-exclamation-triangle-fill', 
        'Insumos con stock actual inferior al mínimo configurado.',
        'warning'
    );
    kpisInsumos += renderKpiCard(
        'Ins. Vencimiento', 
        data.kpis_inventario.insumos_proximos_vencimiento, 
        'Próximos a vencer', 
        'bi-alarm-fill', 
        'Lotes que vencen en los próximos 30 días.',
        'danger'
    );
    kpisInsumos += '</div>';
    sectionInsumos.innerHTML += kpisInsumos;

    // 2. Gráficos Insumos
    let chartsInsumos = '<div class="row g-3">';
    
    // Antigüedad (Donut)
    chartsInsumos += '<div class="col-lg-4 col-md-6">';
    chartsInsumos += createSmartCardHTML('antiguedad-insumos-chart', 'Antigüedad Stock', 'Distribución de lotes por edad.', data.antiguedad_stock_insumos.insight, 'Porcentaje de lotes en cada rango de antigüedad.');
    chartsInsumos += '</div>';

    // Composición (Pie)
    chartsInsumos += '<div class="col-lg-4 col-md-6">';
    chartsInsumos += createSmartCardHTML('composicion-insumos-chart', 'Composición por Categoría', 'Volumen de inventario.', getInsight('composicion_stock_insumos'), 'Cantidad de stock agrupada por categoría.');
    chartsInsumos += '</div>';

    // Valor Stock (Bar - Top N)
    chartsInsumos += '<div class="col-lg-4 col-md-12">';
    chartsInsumos += createSmartCardHTML('valor-stock-insumos-chart', 'Valor Stock Insumos', 'Mayor inversión inmovilizada.', getInsight('valor_stock_insumos'), 'Stock Actual * Precio Unitario.');
    chartsInsumos += '</div>';

    // Stock Crítico (Bar Comparison)
    chartsInsumos += '<div class="col-lg-6">';
    chartsInsumos += createSmartCardHTML('stock-critico-chart', 'Insumos Críticos (Top)', 'Comparativa Actual vs Mínimo.', getInsight('stock_critico'), 'Diferencia entre stock actual y punto de pedido.');
    chartsInsumos += '</div>';

    // Vencimiento (Bar Days)
    chartsInsumos += '<div class="col-lg-6">';
    chartsInsumos += createSmartCardHTML('insumos-vencimiento-chart', 'Próximos Vencimientos', 'Días restantes de vida útil.', getInsight('insumos_vencimiento'), 'Lotes ordenados por fecha de vencimiento más cercana.');
    chartsInsumos += '</div>';

    chartsInsumos += '</div>';
    sectionInsumos.innerHTML += chartsInsumos;


    // --- SECCIÓN: PRODUCTOS ---

    const sectionProductos = document.createElement('div');
    sectionProductos.innerHTML = `<h5 class="mb-4 text-success border-bottom pb-2 mt-4"><i class="bi bi-box2-heart me-2"></i>Gestión de Productos</h5>`;
    container.appendChild(sectionProductos);

    // 1. KPIs Productos
    let kpisProductos = '<div class="row g-3 mb-4">';
    kpisProductos += renderKpiCard(
        'Sin Stock', 
        data.kpis_inventario.productos_cero, 
        'Productos agotados', 
        'bi-dash-circle-fill', 
        'Productos terminados con stock 0.',
        'danger'
    );
    kpisProductos += renderKpiCard(
        'Prod. Vencimiento', 
        data.kpis_inventario.productos_proximos_vencimiento, 
        'Próximos a vencer', 
        'bi-calendar-x-fill', 
        'Lotes que vencen en los próximos 30 días.',
        'warning'
    );
    kpisProductos += '</div>';
    sectionProductos.innerHTML += kpisProductos;

    // 2. Gráficos Productos
    let chartsProductos = '<div class="row g-3">';

    // Antigüedad (Donut)
    chartsProductos += '<div class="col-lg-4 col-md-6">';
    chartsProductos += createSmartCardHTML('antiguedad-productos-chart', 'Antigüedad Stock', 'Distribución de lotes por edad.', data.antiguedad_stock_productos.insight, 'Porcentaje de lotes en cada rango.');
    chartsProductos += '</div>';

    // Distribución Estado (Pie)
    chartsProductos += '<div class="col-lg-4 col-md-6">';
    chartsProductos += createSmartCardHTML('dist-estado-productos-chart', 'Estado del Stock', 'Disponibilidad de inventario.', getInsight('distribucion_estado_productos'), 'Proporción de lotes por estado.');
    chartsProductos += '</div>';

    // Valor Stock (Bar - Top N)
    chartsProductos += '<div class="col-lg-4 col-md-12">';
    chartsProductos += createSmartCardHTML('valor-stock-productos-chart', 'Valor Stock Productos', 'Productos con mayor valoración.', getInsight('valor_stock_productos'), 'Stock * Precio Venta.');
    chartsProductos += '</div>';

    // Cobertura (Horizontal Bar)
    chartsProductos += '<div class="col-lg-6">';
    chartsProductos += createSmartCardHTML('cobertura-productos-chart', 'Cobertura Estimada', 'Días de venta cubiertos.', getInsight('cobertura'), 'Stock / Venta Promedia Diaria.');
    chartsProductos += '</div>';

    // Vencimiento (Bar Days)
    chartsProductos += '<div class="col-lg-6">';
    chartsProductos += createSmartCardHTML('productos-vencimiento-chart', 'Próximos Vencimientos', 'Días restantes de vida útil.', getInsight('productos_vencimiento'), 'Lotes ordenados por fecha de vencimiento.');
    chartsProductos += '</div>';

    chartsProductos += '</div>';
    sectionProductos.innerHTML += chartsProductos;


    // --- INJECT SELECTORS & INTERACTIVITY ---
    const updateTopN = (val) => window.updateCategoryParam('inventario', 'top_n', val);
    
    const injectSelector = (chartId) => {
        const chartDiv = document.getElementById(chartId);
        if (chartDiv) {
            const header = chartDiv.closest('.card').querySelector('.card-header');
            // Check if selector already exists to avoid dupes on re-render
            if (header && !header.querySelector('select')) {
                const selector = createTopNSelector(chartId + '-select', topN, updateTopN);
                header.appendChild(selector);
            }
        }
    };

    injectSelector('valor-stock-insumos-chart');
    injectSelector('valor-stock-productos-chart');
    injectSelector('stock-critico-chart');
    injectSelector('insumos-vencimiento-chart');
    injectSelector('productos-vencimiento-chart');


    // --- RENDER CHARTS ---

    // 1. Antigüedad (Donut - Percentage Focused)
    const renderAntiguedad = (id, dataset, color) => {
        if (hasData(dataset)) {
            createChart(id, {
                tooltip: { 
                    trigger: 'item', 
                    formatter: (params) => {
                        const qty = params.data.quantity != null ? params.data.quantity : 0;
                        // Asumimos que la cantidad puede ser float, mostramos 2 decimales si es necesario
                        const qtyStr = Number(qty).toLocaleString('es-AR', { maximumFractionDigits: 2 });
                        return `${params.name}<br/><b>${params.value} Lotes</b> (${params.percent}%)<br/>Cant: ${qtyStr}`;
                    }
                },
                legend: { orient: 'vertical', right: 10, top: 'center', show: true },
                color: [color, '#fac858', '#ee6666', '#91cc75', '#999999'], // Custom palette incl. grey for 'Sin fecha'
                series: [{ 
                    type: 'pie', 
                    radius: ['40%', '70%'],
                    center: ['40%', '50%'], // Shifted left to accommodate legend
                    itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
                    data: dataset.labels.map((l, i) => ({ 
                        value: dataset.data[i], 
                        name: l,
                        quantity: dataset.quantities ? dataset.quantities[i] : 0
                    }))
                }]
            });
        } else {
            document.getElementById(id).innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted small">Sin datos de antigüedad</div>';
        }
    };

    renderAntiguedad('antiguedad-insumos-chart', data.antiguedad_stock_insumos, '#5470c6');
    renderAntiguedad('antiguedad-productos-chart', data.antiguedad_stock_productos, '#91cc75');


    // 2. Valor Stock (Bar - Currency)
    const renderValueChart = (id, dataset, color) => {
        createChart(id, {
            tooltip: { 
                trigger: 'axis', axisPointer: { type: 'shadow' },
                formatter: (params) => `${params[0].name}<br/>Valor: <b>${formatCurrency(params[0].value)}</b>`
            },
            grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
            xAxis: { 
                type: 'category', 
                data: dataset.labels, 
                axisLabel: { interval: 0, rotate: 30, fontSize: 10, width: 80, overflow: 'truncate' } 
            },
            yAxis: { 
                type: 'value', 
                axisLabel: { 
                    formatter: (val) => {
                        if (val >= 1000000) return `$${(val/1000000).toFixed(1)}M`;
                        if (val >= 1000) return `$${(val/1000).toFixed(0)}k`;
                        return `$${val}`;
                    } 
                } 
            },
            series: [{ 
                type: 'bar', 
                data: dataset.data, 
                itemStyle: { color: color, borderRadius: [4, 4, 0, 0] },
                barMaxWidth: 50
            }]
        });
    };

    renderValueChart('valor-stock-insumos-chart', data.valor_stock_insumos_chart, '#5470c6');
    renderValueChart('valor-stock-productos-chart', data.valor_stock_productos_chart, '#91cc75');


    // 3. Composición (Pie)
    createChart('composicion-insumos-chart', {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', right: 10, top: 'center', show: true },
        series: [{ 
            type: 'pie', radius: '70%', center: ['40%', '50%'],
            data: data.composicion_stock_insumos_chart.labels.map((l, i) => ({ value: data.composicion_stock_insumos_chart.data[i], name: l })),
            itemStyle: { borderRadius: 5 },
            label: { show: false }
        }]
    });

    // 4. Distribución Estado (Donut)
    createChart('dist-estado-productos-chart', {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', right: 10, top: 'center', show: true },
        series: [{ 
            type: 'pie', radius: ['40%', '70%'], center: ['40%', '50%'],
            data: data.distribucion_estado_productos_chart.labels.map((l, i) => ({ value: data.distribucion_estado_productos_chart.data[i], name: l })),
            itemStyle: { borderRadius: 5 },
            label: { show: false }
        }]
    });

    // 5. Stock Crítico (Comparison Bar)
    if (data.stock_critico_chart && data.stock_critico_chart.labels.length > 0) {
        createChart('stock-critico-chart', {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { data: ['Stock Actual', 'Mínimo'], bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: data.stock_critico_chart.labels, axisLabel: { interval: 0, rotate: 30 } },
            yAxis: { type: 'value' },
            series: [
                { name: 'Stock Actual', type: 'bar', data: data.stock_critico_chart.actual, itemStyle: { color: '#ee6666' } },
                { name: 'Mínimo', type: 'bar', data: data.stock_critico_chart.minimo, itemStyle: { color: '#fac858' }, barGap: '-100%', opacity: 0.5 }
            ]
        });
    } else {
        document.getElementById('stock-critico-chart').innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-success small"><i class="bi bi-check-circle me-2"></i>No hay insumos con stock crítico.</div>';
    }

    // 6. Vencimientos (Bar - Days Left)
    const renderExpiration = (id, dataset) => {
        if (dataset && dataset.labels.length > 0) {
            createChart(id, {
                tooltip: { formatter: '{b}: <b>{c} días</b> para vencer' },
                grid: { left: '3%', right: '10%', bottom: '3%', containLabel: true },
                xAxis: { type: 'value', name: 'Días' },
                yAxis: { type: 'category', data: dataset.labels, inverse: true }, // Inverse to show nearest at top
                series: [{ 
                    type: 'bar', 
                    data: dataset.data, 
                    itemStyle: { 
                        color: (params) => params.value < 15 ? '#d9534f' : params.value < 30 ? '#f0ad4e' : '#5bc0de' 
                    },
                    label: { show: true, position: 'right', formatter: '{c} d' }
                }]
            });
        } else {
            document.getElementById(id).innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted small">No hay lotes próximos a vencer.</div>';
        }
    };

    renderExpiration('insumos-vencimiento-chart', data.insumos_vencimiento_chart);
    renderExpiration('productos-vencimiento-chart', data.productos_vencimiento_chart);

    // 7. Cobertura (Horizontal Bar)
    if (data.cobertura_chart && data.cobertura_chart.labels.length > 0) {
        createChart('cobertura-productos-chart', {
            tooltip: { formatter: '{b}: <b>{c} días</b> de cobertura estimada' },
            grid: { containLabel: true },
            xAxis: { type: 'value', name: 'Días' },
            yAxis: { type: 'category', data: data.cobertura_chart.labels },
            series: [{ 
                type: 'bar', 
                data: data.cobertura_chart.data, 
                itemStyle: { color: '#73c0de' },
                markLine: {
                    data: [{ xAxis: 30, name: 'Objetivo Mensual', lineStyle: { color: 'green', type: 'dashed' } }]
                }
            }]
        });
    } else {
        document.getElementById('cobertura-productos-chart').innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted small">Sin datos de ventas para calcular cobertura.</div>';
    }
};