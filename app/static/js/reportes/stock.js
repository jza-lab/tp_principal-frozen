document.addEventListener('DOMContentLoaded', function () {
    const { jsPDF } = window.jspdf;

    // Chart instances
    let insumosComposicionChart, insumosValorChart, productosValorCategoriaChart, productosDistribucionEstadoChart;
    let productosComposicionChart, productosValorChart;

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

    function showNoDataMessage(chart, message = "No hay datos disponibles") {
        if (chart) {
            chart.clear();
            chart.setOption({
                title: {
                    text: message,
                    left: 'center',
                    top: 'center',
                    textStyle: {
                        color: '#888',
                        fontSize: 16
                    }
                }
            });
        }
    }
    
    /**
     * Transforma un objeto de datos {clave: valor} a un array [{name: clave, value: valor}]
     * que es el formato esperado por ECharts para series de tipo 'pie' o 'bar'.
     * Si los datos ya son un array, los devuelve sin cambios.
     * @param {object|Array} data - El objeto o array de datos.
     * @param {string} nameKey - La clave para el nombre/categoría.
     * @param {string} valueKey - La clave para el valor.
     * @returns {Array} - El array de datos transformado.
     */
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
        return []; // Devuelve un array vacío si el formato no es compatible
    }


    // --- RENDER FUNCTIONS ---

    function renderInsumosComposicionChart(data) {
        const chartData = transformDataForChart(data, 'name', 'value');
        if (!chartData || chartData.length === 0) {
            showNoDataMessage(insumosComposicionChart, 'No hay datos de composición');
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
    }

    function renderInsumosValorChart(data) {
        const chartData = transformDataForChart(data, 'nombre', 'valor_total');
        if (!chartData || chartData.length === 0) {
            showNoDataMessage(insumosValorChart, 'No hay datos de valor de insumos');
            return;
        }
        const option = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'category', data: chartData.map(item => item.nombre), axisLabel: { interval: 0, rotate: 30 } },
            yAxis: { type: 'value', name: 'Valor ($)' },
            series: [{ data: chartData.map(item => item.valor_total), type: 'bar', color: azulPaleta[0] }],
            grid: { containLabel: true }
        };
        insumosValorChart.setOption(option);
    }

    function renderInsumosCriticoTable(data) {
        const container = document.getElementById('insumos-critico-table');
        const description = document.getElementById('insumos-critico-description');
        if (!data || data.length === 0) {
            container.innerHTML = '<p>No hay insumos con stock crítico actualmente.</p>';
            description.textContent = 'Total: 0 insumos.';
            return;
        }
        
        let tableHtml = '<ul class="list-group">';
        data.forEach(item => {
            const percentage = (item.stock_actual / item.stock_min) * 100;
            const barColor = percentage < 50 ? 'bg-danger' : 'bg-warning';
            
            tableHtml += `
                <li class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <span>${item.nombre}</span>
                        <span class="fw-bold">${item.stock_actual} / ${item.stock_min} ${item.unidad_medida}</span>
                    </div>
                    <div class="progress mt-1" style="height: 10px;">
                        <div class="progress-bar ${barColor}" role="progressbar" style="width: ${percentage}%;" aria-valuenow="${item.stock_actual}" aria-valuemin="0" aria-valuemax="${item.stock_min}"></div>
                    </div>
                </li>
            `;
        });
        tableHtml += '</ul>';
        container.innerHTML = tableHtml;
        description.textContent = `Total: ${data.length} insumos en estado crítico.`;
    }

    function renderInsumosVencimientoTable(data) {
        const container = document.getElementById('insumos-vencimiento-table');
        if (!data || data.length === 0) {
            container.innerHTML = '<p>No hay lotes de insumos próximos a vencer.</p>';
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
    }

    function renderProductosValorCategoriaChart(data) {
        const chartData = transformDataForChart(data, 'categoria', 'valor_total');
        if (!chartData || chartData.length === 0) {
            showNoDataMessage(productosValorCategoriaChart, 'No hay datos de valor por categoría');
            return;
        }
        const option = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}: ${c}' },
            xAxis: { type: 'category', data: chartData.map(item => item.categoria), axisLabel: { interval: 0, rotate: 30 } },
            yAxis: { type: 'value', name: 'Valor Total ($)' },
            series: [{ data: chartData.map(item => item.valor_total), type: 'bar', color: azulPaleta[3] }],
            grid: { containLabel: true }
        };
        productosValorCategoriaChart.setOption(option);
    }

    function renderProductosDistribucionEstadoChart(data) {
        const chartData = transformDataForChart(data, 'estado', 'cantidad');
        if (!chartData || !chartData.some(item => item.cantidad > 0)) {
            showNoDataMessage(productosDistribucionEstadoChart, 'No hay datos de distribución por estado');
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
    }

    function renderProductosComposicionChart(data) {
        const chartData = transformDataForChart(data, 'name', 'value');
        if (!chartData || chartData.length === 0) {
            showNoDataMessage(productosComposicionChart, 'No hay datos de composición');
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
    }

    function renderProductosValorChart(data) {
        const chartData = transformDataForChart(data, 'nombre', 'valor_total');
        if (!chartData || chartData.length === 0) {
            showNoDataMessage(productosValorChart, 'No hay datos de valor de productos');
            return;
        }
        const option = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'category', data: chartData.map(item => item.nombre), axisLabel: { interval: 0, rotate: 30 } },
            yAxis: { type: 'value', name: 'Valor ($)' },
            series: [{ data: chartData.map(item => item.valor_total), type: 'bar', color: azulPaleta[1] }],
            grid: { containLabel: true }
        };
        productosValorChart.setOption(option);
    }

    function renderProductosBajoStockTable(data) {
        const container = document.getElementById('productos-bajo-stock-table');
        if (!data || data.length === 0) {
            container.innerHTML = '<p>No hay productos con bajo stock.</p>';
            return;
        }
        let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Producto</th><th>Stock Actual</th><th>Stock Mínimo</th></tr></thead><tbody>';
        data.forEach(item => {
            tableHtml += `<tr>
                <td>${item.nombre}</td>
                <td>${item.stock_actual}</td>
                <td>${item.stock_min}</td>
            </tr>`;
        });
        tableHtml += '</tbody></table>';
        container.innerHTML = tableHtml;
    }

    function renderProductosVencimientoTable(data) {
        const container = document.getElementById('productos-vencimiento-table');
        if (!data || data.length === 0) {
            container.innerHTML = '<p>No hay lotes de productos próximos a vencer.</p>';
            return;
        }
        let tableHtml = '<table class="table table-sm table-hover"><thead><tr><th>Producto</th><th>Lote</th><th>Vencimiento</th><th>Cantidad</th></tr></thead><tbody>';
        data.forEach(item => {
            tableHtml += `<tr>
                <td>${item.nombre_producto}</td>
                <td>${item.numero_lote}</td>
                <td>${new Date(item.fecha_vencimiento).toLocaleDateString()}</td>
                <td>${item.cantidad_disponible}</td>
            </tr>`;
        });
        tableHtml += '</tbody></table>';
        container.innerHTML = tableHtml;
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
                return null; // Retornar null para manejarlo en el llamador
            }
        } catch (error) {
            console.error(`Fetch error for ${url}:`, error);
            return null;
        }
    }


    async function loadInsumosData() {
        showLoadingMessage(insumosComposicionChart);
        showLoadingMessage(insumosValorChart);
        showLoadingMessage(productosValorCategoriaChart);
        showLoadingMessage(productosDistribucionEstadoChart);
        
        const topN = document.getElementById('top-n-insumos').value;
        
        const [
            composicionData, valorData, criticoData, vencimientoData, 
            valorCategoriaData, distribucionEstadoData
        ] = await Promise.all([
            fetchData('/reportes/api/stock/insumos/composicion'),
            fetchData(`/reportes/api/stock/insumos/valor?top_n=${topN}`),
            fetchData('/reportes/api/stock/insumos/critico'),
            fetchData('/reportes/api/stock/insumos/vencimiento'),
            fetchData('/reportes/api/stock/productos/valor_por_categoria'),
            fetchData('/reportes/api/stock/productos/distribucion_por_estado')
        ]);

        hideLoading(insumosComposicionChart);
        hideLoading(insumosValorChart);
        hideLoading(productosValorCategoriaChart);
        hideLoading(productosDistribucionEstadoChart);

        renderInsumosComposicionChart(composicionData);
        renderInsumosValorChart(valorData);
        renderInsumosCriticoTable(criticoData);
        renderInsumosVencimientoTable(vencimientoData);
        renderProductosValorCategoriaChart(valorCategoriaData);
        renderProductosDistribucionEstadoChart(distribucionEstadoData);
    }

    async function loadProductosData() {
        showLoadingMessage(productosComposicionChart);
        showLoadingMessage(productosValorChart);

        const topN = document.getElementById('top-n-productos').value;

        const [
            composicionData, valorData, bajoStockData, vencimientoData
        ] = await Promise.all([
            fetchData('/reportes/api/stock/productos/composicion'),
            fetchData(`/reportes/api/stock/productos/valor?top_n=${topN}`),
            fetchData('/reportes/api/stock/productos/bajo_stock'),
            fetchData('/reportes/api/stock/productos/vencimiento')
        ]);
        
        hideLoading(productosComposicionChart);
        hideLoading(productosValorChart);

        renderProductosComposicionChart(composicionData);
        renderProductosValorChart(valorData);
        renderProductosBajoStockTable(bajoStockData);
        renderProductosVencimientoTable(vencimientoData);
    }

    // --- PDF GENERATION ---
    async function generatePDF() {
        downloadPdfBtn.disabled = true;
        downloadPdfBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generando...';

        const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' });
        const today = new Date().toLocaleDateString('es-AR');
        let yPos = 20;
        const pageHeight = pdf.internal.pageSize.getHeight();
        const margin = 15;

        function addHeader(pageNumber) {
            // Placeholder for logo
            pdf.setFontSize(8);
            pdf.text('Logo Empresa', margin, 10);
            pdf.text(`Reporte de Stock - ${today} - Página ${pageNumber}`, pdf.internal.pageSize.getWidth() - margin, 10, { align: 'right' });
        }

        async function addContentToPdf(elementId, title) {
            const element = document.getElementById(elementId);
            if (!element) return;
            
            const isScrollable = element.classList.contains('scrollable-table');
            if(isScrollable) element.classList.add('printable-full-height');

            const canvas = await html2canvas(element, { scale: 2 });

            if(isScrollable) element.classList.remove('printable-full-height');
            
            const imgData = canvas.toDataURL('image/png');
            const imgWidth = 180;
            const imgHeight = (canvas.height * imgWidth) / canvas.width;

            if (yPos + imgHeight + 20 > pageHeight) {
                pdf.addPage();
                yPos = 20;
                addHeader(pdf.internal.pages.length);
            }
            
            pdf.setFontSize(14);
            pdf.text(title, margin, yPos);
            yPos += 8;
            pdf.addImage(imgData, 'PNG', margin, yPos, imgWidth, imgHeight);
            yPos += imgHeight + 10;
        }

        addHeader(1);

        const activeTabId = document.querySelector('.nav-link.active').id;
        
        // Ensure insumos data is loaded and rendered for PDF
        insumosTab.click();
        await new Promise(resolve => setTimeout(resolve, 500));
        
        pdf.setFontSize(18);
        pdf.text('Reporte de Stock de Insumos', margin, yPos);
        yPos += 10;
        
        await addContentToPdf('insumos-composicion-chart', 'Composición del Stock por Categoría');
        await addContentToPdf('insumos-valor-chart', 'Top Insumos por Valor Total');
        await addContentToPdf('insumos-critico-table', 'Insumos con Stock Crítico');
        await addContentToPdf('insumos-vencimiento-table', 'Lotes de Insumos Próximos a Vencer');
        
        // Ensure productos data is loaded and rendered for PDF
        productosTab.click();
        await new Promise(resolve => setTimeout(resolve, 500));
        
        pdf.addPage();
        yPos = 20;
        addHeader(pdf.internal.pages.length);
        
        pdf.setFontSize(18);
        pdf.text('Reporte de Stock de Productos', margin, yPos);
        yPos += 10;

        await addContentToPdf('productos-composicion-chart', 'Composición del Stock por Producto');
        await addContentToPdf('productos-valor-chart', 'Top Productos por Valor en Stock');
        await addContentToPdf('productos-bajo-stock-table', 'Productos con Bajo Stock');
        await addContentToPdf('productos-vencimiento-table', 'Lotes de Productos Próximos a Vencer');
        await addContentToPdf('productos-valor-categoria-chart', 'Valor de Stock por Categoría de Producto');
        await addContentToPdf('productos-distribucion-estado-chart', 'Distribución de Stock por Estado');

        document.getElementById(activeTabId).click();
        
        pdf.save(`reporte_stock_${new Date().toISOString().slice(0,10)}.pdf`);

        downloadPdfBtn.disabled = false;
        downloadPdfBtn.innerHTML = '<i class="fas fa-download fa-sm text-white-50"></i> Generar Reporte';
    }


    // --- INITIALIZATION AND EVENT LISTENERS ---

    function initializeAllCharts() {
        insumosComposicionChart = initChart('insumos-composicion-chart');
        insumosValorChart = initChart('insumos-valor-chart');
        productosValorCategoriaChart = initChart('productos-valor-categoria-chart');
        productosDistribucionEstadoChart = initChart('productos-distribucion-estado-chart');
        
        productosComposicionChart = initChart('productos-composicion-chart');
        productosValorChart = initChart('productos-valor-chart');
    }

    initializeAllCharts();
    
    loadInsumosData().then(() => {
        downloadPdfBtn.disabled = false;
    });

    let productosTabLoaded = false;
    productosTab.addEventListener('shown.bs.tab', function () {
        if(productosComposicionChart) productosComposicionChart.resize();
        if(productosValorChart) productosValorChart.resize();
        
        if (!productosTabLoaded) {
            loadProductosData();
            productosTabLoaded = true;
        }
    });
    
    insumosTab.addEventListener('shown.bs.tab', function() {
        if(insumosComposicionChart) insumosComposicionChart.resize();
        if(insumosValorChart) insumosValorChart.resize();
        if(productosValorCategoriaChart) productosValorCategoriaChart.resize();
        if(productosDistribucionEstadoChart) productosDistribucionEstadoChart.resize();
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

    downloadPdfBtn.addEventListener('click', generatePDF);
    
    window.addEventListener('resize', function () {
        for (const chartId in echartInstances) {
            if (echartInstances.hasOwnProperty(chartId)) {
                echartInstances[chartId].resize();
            }
        }
    });
});
