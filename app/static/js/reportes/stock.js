document.addEventListener('DOMContentLoaded', function () {
    const { jsPDF } = window.jspdf;

    // Chart instances
    let insumosComposicionChart, insumosValorChart;
    let productosComposicionChart, productosValorChart, productosValorCategoriaChart, productosDistribucionEstadoChart, productosRotacionChart, productosCoberturaChart;

    const insumosTab = document.querySelector('#insumos-tab');
    const productosTab = document.querySelector('#productos-tab');
    const downloadPdfBtn = document.getElementById('download-pdf');

    const echartInstances = {};

    const azulPaleta = [
        '#0d6efd', '#0a58ca', '#084298', '#3385ff', '#5c9eff',
        '#85baff', '#aed5ff', '#d6eaff', '#f0f8ff'
    ];

    function initChart(elementId) {
        const chartElement = document.getElementById(elementId);
        if (chartElement) {
            const chart = echarts.init(chartElement);
            echartInstances[elementId] = chart;
            return chart;
        }
        return null;
    }

    function showLoadingMessage(chart, message = 'Cargando datos...') {
        if (chart) {
            chart.showLoading('default', {
                text: message,
                color: '#0d6efd',
                textColor: '#333',
                maskColor: 'rgba(255, 255, 255, 0.8)',
                zlevel: 0
            });
        }
    }

    function hideLoading(chart) {
        if (chart) {
            chart.hideLoading();
        }
    }

    function showNoDataMessage(chart, summaryId, message = "No hay datos disponibles") {
    const summaryEl = document.getElementById(summaryId);
    if (chart) {
        chart.clear();
        chart.setOption({
            title: {
                text: message,
                left: 'center',
                top: 'center',
                textStyle: { color: '#888', fontSize: 16 }
            }
        });
    }
    if (summaryEl) {
        summaryEl.innerHTML = `<p class="text-center text-muted">${message}</p>`;
    }
}
    
    function transformDataForChart(data, nameKey = 'name', valueKey = 'value') {
        if (Array.isArray(data)) {
            return data;
        }
        if (typeof data === 'object' && data !== null) {
            return Object.entries(data).map(([key, val]) => ({
                [nameKey]: key,
                [valueKey]: val
            }));
        }
        return [];
    }


    // --- RENDER FUNCTIONS ---

    function renderInsumosComposicionChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('insumos-composicion-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(insumosComposicionChart, 'insumos-composicion-summary', 'No hay datos de composición');
        return;
    }

    const option = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', type: 'scroll' },
        series: [{
            name: 'Composición', type: 'pie', radius: ['40%', '70%'],
            avoidLabelOverlap: false, label: { show: false, position: 'center' },
            emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold' } },
            labelLine: { show: false }, data: chartData, color: azulPaleta
        }]
    };
    insumosComposicionChart.setOption(option);
    
    // Summary
    const highest = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
    summaryEl.innerHTML = `La categoría con más stock es <strong>${highest.name}</strong>, representando la mayor parte del inventario de insumos.`;
}

function renderInsumosValorChart(data) {
    const chartData = transformDataForChart(data, 'nombre', 'valor');
     const summaryEl = document.getElementById('insumos-valor-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(insumosValorChart, 'insumos-valor-summary', 'No hay datos de valor de insumos');
        return;
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}: ${c}' },
        xAxis: { type: 'category', data: chartData.map(item => item.nombre), axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: 'Valor ($)' },
        series: [{ data: chartData.map(item => item.valor), type: 'bar', color: azulPaleta[0] }],
        grid: { containLabel: true }
    };
    insumosValorChart.setOption(option);

    // Summary
    const mostValuable = chartData[0];
    summaryEl.innerHTML = `El insumo más valioso en stock es <strong>${mostValuable.nombre}</strong> con un valor total de <strong>$${mostValuable.valor.toLocaleString('es-AR')}</strong>.`;
}

function renderInsumosCriticoTable(data) {
    const container = document.getElementById('insumos-critico-table');
    const summaryEl = document.getElementById('insumos-critico-summary');

    if (!data || data.length === 0) {
        container.innerHTML = '<p>No hay insumos con stock crítico actualmente.</p>';
        summaryEl.innerHTML = 'Actualmente, no hay insumos por debajo de su nivel de stock mínimo definido.';
        return;
    }
    
    let tableHtml = '<ul class="list-group">';
    data.forEach(item => {
        const percentage = (item.stock_actual / item.stock_minimo) * 100;
        const barColor = percentage < 50 ? 'bg-danger' : 'bg-warning';
        
        tableHtml += `
            <li class="list-group-item">
                <div class="d-flex justify-content-between align-items-center">
                    <span>${item.nombre}</span>
                    <span class="fw-bold">${item.stock_actual} / ${item.stock_min} ${item.unidad_medida}</span>
                </div>
                <div class="progress mt-1" style="height: 10px;">
                    <div class="progress-bar ${barColor}" role="progressbar" style="width: ${percentage}%;" aria-valuenow="${item.stock_actual}" aria-valuemin="0" aria-valuemax="${item.stock_minimo}"></div>
                </div>
            </li>
        `;
    });
    tableHtml += '</ul>';
    container.innerHTML = tableHtml;

    // Summary
    summaryEl.innerHTML = `Se han identificado <strong>${data.length}</strong> insumos en estado crítico. El más urgente es <strong>${data[0].nombre}</strong>.`;
}

function renderInsumosVencimientoTable(data) {
    const container = document.getElementById('insumos-vencimiento-table');
    const summaryEl = document.getElementById('insumos-vencimiento-summary');

    if (!data || data.length === 0) {
        container.innerHTML = '<p>No hay lotes de insumos próximos a vencer.</p>';
        summaryEl.innerHTML = 'No hay lotes de insumos con fecha de vencimiento en los próximos 30 días.';
        return;
    }

    let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Insumo</th><th>Lote</th><th>Vencimiento</th><th>Cantidad</th></tr></thead><tbody>';
    data.forEach(item => {
        tableHtml += `<tr>
            <td>${item.nombre_insumo}</td>
            <td>${item.numero_lote}</td>
            <td>${new Date(item.fecha_vencimiento).toLocaleDateString()}</td>
            <td>${item.cantidad_disponible} ${item.unidad_medida}</td>
        </tr>`;
    });
    tableHtml += '</tbody></table>';
    container.innerHTML = tableHtml;

    // Summary
    const closest = data[0];
    summaryEl.innerHTML = `Hay <strong>${data.length}</strong> lotes próximos a vencer. El más cercano es el lote <strong>${closest.numero_lote}</strong> de <strong>${closest.nombre_insumo}</strong>, que vence el <strong>${new Date(closest.fecha_vencimiento).toLocaleDateString()}</strong>.`;
}

function renderProductosComposicionChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('productos-composicion-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(productosComposicionChart, 'productos-composicion-summary', 'No hay datos de composición');
        return;
    }

    const option = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', type: 'scroll' },
        series: [{
            name: 'Composición', type: 'pie', radius: '50%', data: chartData,
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
            color: azulPaleta
        }]
    };
    productosComposicionChart.setOption(option);

    const highest = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
    summaryEl.innerHTML = `El producto con más stock es <strong>${highest.name}</strong>, representando la mayor parte del inventario.`;
}

function renderProductosValorChart(data) {
    const chartData = transformDataForChart(data, 'nombre', 'valor');
    const summaryEl = document.getElementById('productos-valor-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(productosValorChart, 'productos-valor-summary', 'No hay datos de valor de productos');
        return;
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: chartData.map(item => item.nombre), axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: 'Valor ($)' },
        series: [{ data: chartData.map(item => item.valor), type: 'bar', color: azulPaleta[1] }],
        grid: { containLabel: true }
    };
    productosValorChart.setOption(option);

    const mostValuable = chartData[0];
    summaryEl.innerHTML = `El producto más valioso en stock es <strong>${mostValuable.nombre}</strong> con un valor total de <strong>$${mostValuable.valor.toLocaleString('es-AR')}</strong>.`;
}


function renderProductosValorCategoriaChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('productos-valor-categoria-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(productosValorCategoriaChart, 'productos-valor-categoria-summary', 'No hay datos de valor por categoría');
        return;
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}: ${c}' },
        xAxis: { type: 'category', data: chartData.map(item => item.name), axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: 'Valor Total ($)' },
        series: [{ data: chartData.map(item => item.value), type: 'bar', color: azulPaleta[3] }],
        grid: { containLabel: true }
    };
    productosValorCategoriaChart.setOption(option);

    // Summary
    const mostValuableCat = chartData[0];
    summaryEl.innerHTML = `La categoría <strong>${mostValuableCat.name}</strong> es la que más capital concentra, con un valor de <strong>$${mostValuableCat.value.toLocaleString('es-AR')}</strong>.`;
}

function renderProductosDistribucionEstadoChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('productos-distribucion-summary');
    
    if (!chartData || !chartData.some(item => item.value > 0)) {
        showNoDataMessage(productosDistribucionEstadoChart, 'productos-distribucion-summary', 'No hay datos de distribución por estado');
        return;
    }

    const option = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { top: 'bottom' },
        series: [{
            name: 'Distribución', type: 'pie', radius: '50%', data: chartData,
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
            color: azulPaleta.slice(2)
        }]
    };
    productosDistribucionEstadoChart.setOption(option);

    // Summary
    const largestState = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
    summaryEl.innerHTML = `El estado predominante del stock es <strong>${largestState.name}</strong>, agrupando la mayor cantidad de unidades de producto.`;
}


function renderProductosRotacionChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('productos-rotacion-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(productosRotacionChart, 'productos-rotacion-summary', 'No hay datos de rotación');
        return;
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: chartData.map(item => item.name), axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: 'Cantidad Vendida' },
        series: [{ data: chartData.map(item => item.value), type: 'bar', color: azulPaleta[2] }],
        grid: { containLabel: true }
    };
    productosRotacionChart.setOption(option);
    
    // Summary
    const topSeller = chartData[0];
    summaryEl.innerHTML = `El producto más vendido en los últimos 30 días es <strong>${topSeller.name}</strong>, con <strong>${topSeller.value}</strong> unidades vendidas.`;
}

function renderProductosCoberturaChart(data) {
    const chartData = transformDataForChart(data, 'name', 'value');
    const summaryEl = document.getElementById('productos-cobertura-summary');

    if (!chartData || chartData.length === 0) {
        showNoDataMessage(productosCoberturaChart, 'productos-cobertura-summary', 'No hay datos de cobertura');
        return;
    }

    const option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: chartData.map(item => item.name), axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: 'Días de Cobertura' },
        series: [{ data: chartData.map(item => item.value), type: 'bar', color: azulPaleta[4] }],
        grid: { containLabel: true }
    };
    productosCoberturaChart.setOption(option);

    // Summary
    const lowestCoverage = chartData[0];
    summaryEl.innerHTML = `El producto con menor cobertura es <strong>${lowestCoverage.name}</strong>, con stock para aproximadamente <strong>${lowestCoverage.value}</strong> días.`;
}

function renderProductosBajoStockTable(data) {
    const container = document.getElementById('productos-bajo-stock-table');
    const summaryEl = document.getElementById('productos-bajo-stock-summary');

    if (!data || data.length === 0) {
        container.innerHTML = '<p>No hay productos con bajo stock.</p>';
        summaryEl.innerHTML = 'Todos los productos se encuentran por encima de su nivel de stock mínimo.';
        return;
    }

    let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Producto</th><th>Stock Actual</th><th>Stock Mínimo</th></tr></thead><tbody>';
    data.forEach(item => {
        const stockActualDisplay = item.stock_actual > 0
            ? item.stock_actual
            : '<span class="text-danger fw-bold">No disponible</span>';

        tableHtml += `<tr>
            <td>${item.nombre}</td>
            <td>${stockActualDisplay}</td>
            <td>${item.stock_minimo}</td>
        </tr>`;
    });
    tableHtml += '</tbody></table>';
    container.innerHTML = tableHtml;

    // Summary
    const zeroStockCount = data.filter(item => item.stock_actual === 0).length;
    summaryEl.innerHTML = `Hay <strong>${data.length}</strong> productos en estado de bajo stock, de los cuales <strong>${zeroStockCount}</strong> se encuentran agotados.`;
}


function renderProductosVencimientoTable(data) {
    const container = document.getElementById('productos-vencimiento-table');
    const summaryEl = document.getElementById('productos-vencimiento-summary');

    if (!data || data.length === 0) {
        container.innerHTML = '<p>No hay lotes de productos próximos a vencer.</p>';
        summaryEl.innerHTML = 'Ningún lote de producto terminado tiene fecha de vencimiento en los próximos 30 días.';
        return;
    }

    let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Producto</th><th>Lote</th><th>Vencimiento</th><th>Cantidad</th></tr></thead><tbody>';
    data.forEach(item => {
        tableHtml += `<tr>
            <td>${item.producto.nombre}</td>
            <td>${item.numero_lote}</td>
            <td>${new Date(item.fecha_vencimiento).toLocaleDateString()}</td>
            <td>${item.cantidad_actual}</td>
        </tr>`;
    });
    tableHtml += '</tbody></table>';
    container.innerHTML = tableHtml;

    // Summary
    const closest = data[0];
    summaryEl.innerHTML = `Se encontraron <strong>${data.length}</strong> lotes próximos a vencer. El más crítico es el lote <strong>${closest.numero_lote}</strong> de <strong>${closest.producto_nombre}</strong>.`;
}
    // --- DATA FETCHING ---

    async function fetchData(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            if (result.success) {
                return result.data;
            } else {
                console.error(`API error for ${url}:`, result.error);
                return null;
            }
        } catch (error) {
            console.error(`Fetch error for ${url}:`, error);
            return null;
        }
    }


    async function loadInsumosData() {
        showLoadingMessage(insumosComposicionChart);
        showLoadingMessage(insumosValorChart);
        
        const topN = document.getElementById('top-n-insumos').value;
        
        const [
            composicionData, valorData, criticoData, vencimientoData
        ] = await Promise.all([
            fetchData('/reportes/api/stock/insumos/composicion'),
            fetchData(`/reportes/api/stock/insumos/valor?top_n=${topN}`),
            fetchData('/reportes/api/stock/insumos/critico'),
            fetchData('/reportes/api/stock/insumos/vencimiento')
        ]);

        hideLoading(insumosComposicionChart);
        hideLoading(insumosValorChart);

        renderInsumosComposicionChart(composicionData);
        renderInsumosValorChart(valorData);
        renderInsumosCriticoTable(criticoData);
        renderInsumosVencimientoTable(vencimientoData);
    }

    async function loadProductosData() {
        showLoadingMessage(productosComposicionChart);
        showLoadingMessage(productosValorChart);
        showLoadingMessage(productosValorCategoriaChart);
        showLoadingMessage(productosDistribucionEstadoChart);
        showLoadingMessage(productosRotacionChart);
        showLoadingMessage(productosCoberturaChart);

        const topN = document.getElementById('top-n-productos').value;

        const [
            composicionData, valorData, bajoStockData, vencimientoData,
            valorCategoriaData, distribucionEstadoData, rotacionData, coberturaData
        ] = await Promise.all([
            fetchData('/reportes/api/stock/productos/composicion'),
            fetchData(`/reportes/api/stock/productos/valor?top_n=${topN}`),
            fetchData('/reportes/api/stock/productos/bajo_stock'),
            fetchData('/reportes/api/stock/productos/vencimiento'),
            fetchData('/reportes/api/stock/productos/valor_por_categoria'),
            fetchData('/reportes/api/stock/productos/distribucion_por_estado'),
            fetchData('/reportes/api/stock/productos/rotacion'),
            fetchData('/reportes/api/stock/productos/cobertura')
        ]);
        
        hideLoading(productosComposicionChart);
        hideLoading(productosValorChart);
        hideLoading(productosValorCategoriaChart);
        hideLoading(productosDistribucionEstadoChart);
        hideLoading(productosRotacionChart);
        hideLoading(productosCoberturaChart);

        renderProductosComposicionChart(composicionData);
        renderProductosValorChart(valorData);
        renderProductosBajoStockTable(bajoStockData);
        renderProductosVencimientoTable(vencimientoData);
        renderProductosValorCategoriaChart(valorCategoriaData);
        renderProductosDistribucionEstadoChart(distribucionEstadoData);
        renderProductosRotacionChart(rotacionData);
        renderProductosCoberturaChart(coberturaData);
    }

    // --- PDF GENERATION ---
    async function generatePDF() {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const contentWidth = pageWidth - margin * 2;
        let yPos = margin;

        const activeTabPane = document.querySelector('.tab-pane.active.show');
        if (!activeTabPane) {
            console.error("No se encontró una pestaña activa para generar el PDF.");
            return;
        }

        const reportTitle = "Reporte de Stock - " + (activeTabPane.id === 'insumos' ? 'Insumos' : 'Productos Terminados');
        
        pdf.setFontSize(18);
        pdf.text(reportTitle, margin, yPos);
        yPos += 15;

        const cards = activeTabPane.querySelectorAll('.card');

        for (const card of cards) {
            const canvas = await html2canvas(card, { scale: 2 });
            const imgData = canvas.toDataURL('image/png');
            const imgHeight = (canvas.height * contentWidth) / canvas.width;

            if (yPos + imgHeight > pageHeight - margin) {
                pdf.addPage();
                yPos = margin;
                pdf.setFontSize(12);
                pdf.text(reportTitle + " (Continuación)", margin, yPos);
                yPos += 10;
            }

            pdf.addImage(imgData, 'PNG', margin, yPos, contentWidth, imgHeight);
            yPos += imgHeight + 10;
        }

        pdf.save(`reporte_stock_${activeTabPane.id}.pdf`);
    }


    // --- INITIALIZATION AND EVENT LISTENERS ---

    function initializeAllCharts() {
        insumosComposicionChart = initChart('insumos-composicion-chart');
        insumosValorChart = initChart('insumos-valor-chart');
        
        productosComposicionChart = initChart('productos-composicion-chart');
        productosValorChart = initChart('productos-valor-chart');
        productosValorCategoriaChart = initChart('productos-valor-categoria-chart');
        productosDistribucionEstadoChart = initChart('productos-distribucion-estado-chart');
        productosRotacionChart = initChart('productos-rotacion-chart');
        productosCoberturaChart = initChart('productos-cobertura-chart');
    }

    initializeAllCharts();
    
    loadInsumosData().then(() => {
        downloadPdfBtn.disabled = false;
    });

    let productosTabLoaded = false;
    productosTab.addEventListener('shown.bs.tab', function () {
        if(productosComposicionChart) productosComposicionChart.resize();
        if(productosValorChart) productosValorChart.resize();
        if(productosValorCategoriaChart) productosValorCategoriaChart.resize();
        if(productosDistribucionEstadoChart) productosDistribucionEstadoChart.resize();
        if(productosRotacionChart) productosRotacionChart.resize();
        if(productosCoberturaChart) productosCoberturaChart.resize();
        
        if (!productosTabLoaded) {
            loadProductosData();
            productosTabLoaded = true;
        }
    });
    
    insumosTab.addEventListener('shown.bs.tab', function() {
        if(insumosComposicionChart) insumosComposicionChart.resize();
        if(insumosValorChart) insumosValorChart.resize();
    });

    document.getElementById('top-n-insumos').addEventListener('change', async function () {
        showLoadingMessage(insumosValorChart);
        const topN = this.value;
        const data = await fetchData(`/reportes/api/stock/insumos/valor?top_n=${topN}`);
        hideLoading(insumosValorChart);
        renderInsumosValorChart(data);
    });

    document.getElementById('top-n-productos').addEventListener('change', async function () {
        showLoadingMessage(productosValorChart);
        const topN = this.value;
        const data = await fetchData(`/reportes/api/stock/productos/valor?top_n=${topN}`);
        hideLoading(productosValorChart);
        renderProductosValorChart(data);
    });

    downloadPdfBtn.addEventListener('click', async function() {
        const originalText = downloadPdfBtn.innerHTML;
        downloadPdfBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            Generando...
        `;
        downloadPdfBtn.disabled = true;

        try {
            await generatePDF();
        } catch (error) {
            console.error("Error al generar el PDF:", error);
            alert("Hubo un error al generar el PDF. Por favor, intente de nuevo.");
        } finally {
            downloadPdfBtn.innerHTML = originalText;
            downloadPdfBtn.disabled = false;
        }
    });
    
    window.addEventListener('resize', function () {
        for (const chartId in echartInstances) {
            if (echartInstances.hasOwnProperty(chartId)) {
                echartInstances[chartId].resize();
            }
        }
    });
});
