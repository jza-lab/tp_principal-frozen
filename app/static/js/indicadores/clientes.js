// app/static/js/indicadores/clientes.js

window.renderComercial = async function(data, container, utils) {
    const { renderKpiCard, createSmartCardHTML, createChart } = utils;

    // --- 1. KPIs Numéricos (Fila Superior) ---
    let content = '<div class="row g-3 mb-4">';
    
    content += renderKpiCard(
        'Cumplimiento', 
        `${data.kpis_comerciales.cumplimiento_pedidos.valor.toFixed(1)}%`, 
        `${data.kpis_comerciales.cumplimiento_pedidos.completados} / ${data.kpis_comerciales.cumplimiento_pedidos.total} total`, 
        'bi-box-seam',
        '<b>Fórmula:</b> (Pedidos Completados / Total Pedidos).<br>Incluye pedidos cancelados en el total.'
    );
    
    content += renderKpiCard(
        'Ticket Medio', 
        `$${data.kpis_comerciales.valor_promedio_pedido.valor.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`, 
        `${data.kpis_comerciales.valor_promedio_pedido.num_pedidos} pedidos válidos`, 
        'bi-receipt',
        '<b>Fórmula:</b> (Ingresos Totales / Número de Pedidos Válidos).<br>Se excluyen los pedidos cancelados.'
    );

    content += renderKpiCard(
        'Ingresos Totales', 
        `$${data.kpis_comerciales.ingresos_totales.valor.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`, 
        `${data.kpis_comerciales.ingresos_totales.num_pedidos} pedidos generados`, 
        'bi-cash-coin',
        '<b>Fórmula:</b> Suma del valor de todos los pedidos generados en el periodo (excluyendo cancelados).'
    );

    content += '</div>';

    // --- 2. Título Sección Gráficos ---
    content += `
    <div class="d-flex align-items-center mb-4">
        <hr class="flex-grow-1">
        <span class="px-3 text-muted small text-uppercase fw-bold">Análisis de Ventas y Clientes</span>
        <hr class="flex-grow-1">
    </div>`;

    // --- 3. Gráficos (Smart Cards) ---
    content += '<div class="row g-3 mb-4 align-items-stretch">';

    // Chart 1: Evolución de Ingresos (Line Chart Comparison)
    content += '<div class="col-lg-6 col-xl-6">';
    content += createSmartCardHTML(
        'chart-evolucion-ventas',
        'Evolución de Ingresos',
        'Comparativa de ingresos por ventas vs periodo anterior.',
        data.evolucion_ventas.insight,
        data.evolucion_ventas.tooltip
    );
    content += '</div>';

    // Chart 2: Distribución de Estados (Pie Chart)
    content += '<div class="col-lg-6 col-xl-6">';
    content += createSmartCardHTML(
        'chart-estados-pedidos',
        'Estados de Pedidos',
        'Distribución actual de los estados de pedidos en el periodo.',
        data.distribucion_estados.insight,
        data.distribucion_estados.tooltip
    );
    content += '</div>';

    // Chart 3: Top Clientes (Bar Chart)
    content += '<div class="col-lg-6 col-xl-6">';
    content += createSmartCardHTML(
        'chart-top-clientes',
        'Top Clientes (Gasto Total)',
        'Clientes con mayor volumen de compra (incluye pedidos en proceso).',
        data.top_clientes.insight,
        data.top_clientes.tooltip
    );
    content += '</div>';

    // Chart 4: Motivos Notas de Crédito (Pie/Bar Chart)
    content += '<div class="col-lg-6 col-xl-6">';
    content += createSmartCardHTML(
        'chart-motivos-nc',
        'Notas de Crédito',
        'Clasificación de motivos para generación de notas de crédito.',
        data.motivos_notas_credito.insight,
        data.motivos_notas_credito.tooltip
    );
    content += '</div>';

    content += '</div>'; // End Row

    container.innerHTML = content;

    // --- 4. Render Charts ---

    // Chart 1: Evolución Ventas
    createChart('chart-evolucion-ventas', {
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0, left: 'center' },
        grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
        xAxis: { 
            type: 'category', 
            boundaryGap: false, 
            data: data.evolucion_ventas.categories 
        },
        yAxis: { type: 'value' },
        series: data.evolucion_ventas.series.map(s => ({
            name: s.name,
            type: 'line',
            smooth: true, // Lineas suaves
            data: s.data,
            showSymbol: false,
            lineStyle: { width: 3 },
            emphasis: { focus: 'series' }
        }))
    });

    // Chart 2: Estados Pedidos (Pie)
    createChart('chart-estados-pedidos', {
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, left: 'center', type: 'scroll' },
        series: [{
            name: 'Estado',
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '45%'],
            itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
            data: data.distribucion_estados.data
        }]
    });

    // Chart 3: Top Clientes (Dynamic: Pie if <= 5, Bar if > 5)
    let topClientesOption = {};
    if (data.top_clientes.categories.length <= 5) {
        const pieData = data.top_clientes.categories.map((cat, i) => ({
            name: cat,
            value: data.top_clientes.values[i]
        }));
        topClientesOption = {
            tooltip: { trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
            legend: { bottom: 0, left: 'center' },
            series: [{
                name: 'Gasto Total',
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['50%', '45%'],
                data: pieData,
                itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 }
            }]
        };
    } else {
        topClientesOption = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { 
                type: 'category', 
                data: data.top_clientes.categories,
                axisLabel: { width: 100, overflow: 'truncate' } 
            },
            series: [{
                name: 'Gasto Total',
                type: 'bar',
                data: data.top_clientes.values,
                itemStyle: { color: '#5470C6', borderRadius: [0, 4, 4, 0] },
                label: { show: true, position: 'right', formatter: '${c}' }
            }]
        };
    }
    createChart('chart-top-clientes', topClientesOption);

    // Chart 4: Motivos Notas Crédito
    const ncData = data.motivos_notas_credito;
    let ncOption = {};
    
    if (ncData.chart_type === 'pie') {
        ncOption = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, left: 'center' },
            series: [{
                name: 'Motivo',
                type: 'pie',
                radius: '60%',
                center: ['50%', '45%'],
                data: ncData.data,
                itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 }
            }]
        };
    } else {
        // Bar chart for many categories
        ncOption = {
             tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
             grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
             xAxis: { type: 'value' },
             yAxis: { type: 'category', data: ncData.data.categories },
             series: [{
                 name: 'Cantidad',
                 type: 'bar',
                 data: ncData.data.values,
                 itemStyle: { color: '#EE6666' },
                 label: { show: true, position: 'right' }
             }]
        };
    }
    createChart('chart-motivos-nc', ncOption);
};
