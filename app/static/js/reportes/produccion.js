document.addEventListener('DOMContentLoaded', function () {
    const bluePalette = ['#003f5c', '#374c80', '#7a5195', '#bc5090', '#ffa600', '#007bff', '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e'];
    let charts = {};

    const reportContainer = document.getElementById('report-container');
    const noDataMessage = document.getElementById('no-data-message');
    const downloadButton = document.getElementById('download-pdf');

    function updateDescription(elementId, text) {
        const el = document.getElementById(elementId);
        if (el) {
            el.innerHTML = text;
        }
    }

    const apiEndpoints = [
        { key: 'ordenes', url: '/reportes/api/produccion/ordenes_por_estado' },
        { key: 'composicion', url: '/reportes/api/produccion/composicion_produccion' },
        { key: 'tiempoCiclo', url: '/reportes/api/produccion/tiempo_ciclo_promedio' },
        { key: 'produccionTiempo', url: '/reportes/api/produccion/produccion_por_tiempo' }
    ];

    Promise.all(apiEndpoints.map(ep => fetch(ep.url).then(res => res.json())))
        .then(results => {
            const dataMap = results.reduce((map, result, index) => {
                map[apiEndpoints[index].key] = result.data || {};
                return map;
            }, {});

            const hasData = Object.values(dataMap).some(data => Object.keys(data).length > 0);

            if (!hasData) {
                if(reportContainer) reportContainer.style.display = 'none';
                if(noDataMessage) noDataMessage.style.display = 'block';
                if(downloadButton) downloadButton.disabled = true;
                return;
            }

            if(reportContainer) reportContainer.style.display = 'block';
            if(noDataMessage) noDataMessage.style.display = 'none';
            if(downloadButton) downloadButton.disabled = false;

            renderOrdenesChart(dataMap.ordenes);
            renderComposicionChart(dataMap.composicion);
            renderTiempoCiclo(dataMap.tiempoCiclo);
            loadTopInsumosChart();
            renderProduccionTiempoChart(dataMap.produccionTiempo);

        }).catch(error => {
            console.error("Error fetching report data:", error);
            if(reportContainer) reportContainer.style.display = 'none';
            if(noDataMessage) noDataMessage.style.display = 'block';
            if(noDataMessage) noDataMessage.textContent = 'Error al cargar los datos. Por favor, intente más tarde.';
            if(downloadButton) downloadButton.disabled = true;
        });

    function renderOrdenesChart(data) {
        const container = document.getElementById('ordenes-por-estado-chart');
        if (!container || !data || Object.keys(data).length === 0) {
            updateDescription('ordenes-por-estado-description', 'No hay datos de órdenes para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['ordenes'] = {chart: chart, title: 'Órdenes por Estado'};
        const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
        const totalOrders = chartData.reduce((sum, item) => sum + item.value, 0);
        const mostFrequent = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
        const percentage = ((mostFrequent.value / totalOrders) * 100).toFixed(1);
        const description = `Actualmente, el estado más común es <strong>${mostFrequent.name}</strong>, con ${mostFrequent.value} de ${totalOrders} órdenes (${percentage}% del total).`;
        updateDescription('ordenes-por-estado-description', description);
        charts['ordenes'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 10, left: 'center', type: 'scroll' },
            series: [{ name: 'Órdenes', type: 'pie', radius: ['50%', '70%'], center: ['50%', '40%'], avoidLabelOverlap: false, label: { show: false }, emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold', formatter: '{b}\n{c}' } }, labelLine: { show: false }, data: chartData }],
            color: bluePalette
        };
        chart.setOption(option);
    }

    function renderComposicionChart(data) {
        const container = document.getElementById('composicion-produccion-chart');
        if (!container || !data || Object.keys(data).length === 0) {
            updateDescription('composicion-produccion-description', 'No hay datos de producción para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['composicion'] = {chart: chart, title: 'Composición de la Producción'};
        const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
        const totalQuantity = chartData.reduce((sum, item) => sum + item.value, 0);
        const topProduct = chartData.reduce((max, item) => item.value > max.value ? item : max, chartData[0]);
        const description = `Se planifica producir un total de <strong>${totalQuantity.toLocaleString('es-AR')} unidades</strong>. El producto con mayor demanda es <strong>${topProduct.name}</strong>.`;
        updateDescription('composicion-produccion-description', description);
        charts['composicion'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'item' },
            legend: { bottom: 10, left: 'center', type: 'scroll' },
            series: [{ name: 'Cantidad', type: 'pie', radius: '50%', center: ['50%', '40%'], data: chartData, emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } } }],
            color: bluePalette.slice(2)
        };
        chart.setOption(option);
    }

    function renderTiempoCiclo(data) {
        if (!data || Object.keys(data).length === 0) {
            updateDescription('tiempo-ciclo-description', 'No hay suficientes órdenes completadas para calcular un promedio.');
            return;
        }
        const { dias, horas, minutos } = data;
        document.getElementById('tiempo-ciclo-promedio').textContent = `${dias}d ${horas}h ${minutos}m`;
        const description = `Este es el tiempo promedio que transcurre desde que una orden de producción inicia hasta que se marca como completada.`;
        updateDescription('tiempo-ciclo-description', description);
    }

    function renderProduccionTiempoChart(data) {
        const container = document.getElementById('produccion-por-tiempo-chart');
        if (!container || !data || Object.keys(data).length === 0) {
            updateDescription('produccion-por-tiempo-description', 'No hay datos de producción histórica para mostrar.');
            return;
        }
        const chart = echarts.init(container);
        charts['produccionTiempo'] = {chart: chart, title: 'Producción a lo largo del tiempo'};
        const timePeriods = Object.keys(data).length;
        const totalCompleted = Object.values(data).reduce((sum, val) => sum + val, 0);
        const average = (totalCompleted / timePeriods).toFixed(1);
        const description = `Se han completado un total de <strong>${totalCompleted}</strong> órdenes en los últimos <strong>${timePeriods}</strong> periodos, con un promedio de <strong>${average}</strong> órdenes por semana.`;
        updateDescription('produccion-por-tiempo-description', description);
        charts['produccionTiempo'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');
        const option = {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'category', data: Object.keys(data) },
            yAxis: { type: 'value' },
            series: [{ data: Object.values(data), type: 'line', smooth: true, areaStyle: {} }],
            color: bluePalette[4]
        };
        chart.setOption(option);
    }

    const topNSelect = document.getElementById('top-n-select');
    if (topNSelect) {
        topNSelect.addEventListener('change', (event) => {
            loadTopInsumosChart(event.target.value);
        });
    }

    function loadTopInsumosChart(topN = 5) {
        const container = document.getElementById('top-insumos-chart');
        if (!container) return;
        
        const chart = echarts.getInstanceByDom(container) || echarts.init(container);
        charts['topInsumos'] = {chart: chart, title: `Top ${topN} Insumos Utilizados`};

        fetch(`/reportes/api/produccion/top_insumos?top_n=${topN}`)
            .then(response => response.json())
            .then(result => {
                if (result.success && Object.keys(result.data).length > 0) {
                    const data = Object.entries(result.data).map(([name, value]) => ({ name, value }));
                    const topInsumo = data.reduce((max, item) => item.value > max.value ? item : max, data[0]);
                    const description = `El insumo más utilizado es <strong>${topInsumo.name}</strong>, con un consumo total de <strong>${topInsumo.value.toLocaleString('es-AR')} unidades</strong>.`;
                    updateDescription('top-insumos-description', description);
                    charts['topInsumos'].description = description.replace(/<strong>/g, '').replace(/<\/strong>/g, '');

                    const option = {
                        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                        grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
                        xAxis: { type: 'value', boundaryGap: [0, 0.01] },
                        yAxis: { type: 'category', data: data.map(item => item.name).reverse() },
                        series: [{ name: 'Cantidad Utilizada', type: 'bar', data: data.map(item => item.value).reverse() }],
                        color: bluePalette[1]
                    };
                    chart.setOption(option, true);
                } else {
                    updateDescription('top-insumos-description', 'No hay datos de consumo de insumos para mostrar.');
                }
            });
    }
        
    if(downloadButton){
        // Remove existing listeners if possible, or use a flag.
        // Since we can't easily remove anonymous listeners, we clone and replace the node to clear them.
        const newDownloadButton = downloadButton.cloneNode(true);
        downloadButton.parentNode.replaceChild(newDownloadButton, downloadButton);

        newDownloadButton.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generando...';
            
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = pdf.internal.pageSize.getHeight();
            const margin = 15;
            let yPos = 0;
            let page = 1;

            async function getImageBase64(url) {
                const response = await fetch(url);
                const blob = await response.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }

            try {
                const logoBase64 = await getImageBase64('/static/img/icon.png');

                // Re-define logic inside the new listener scope or ensure it's accessible
                const pdf = new jsPDF('p', 'mm', 'a4');
                const pdfWidth = pdf.internal.pageSize.getWidth();
                const pdfHeight = pdf.internal.pageSize.getHeight();
                const margin = 15;
                let yPos = 0;
                let page = 1;

                function addHeader() {
                    if (logoBase64) {
                        pdf.addImage(logoBase64, 'PNG', margin, 10, 10, 10);
                    }
                    pdf.setFontSize(18);
                    pdf.setFont('helvetica', 'bold');
                    pdf.text('FrozenProd Inc.', margin + 12, 18);
                    pdf.setFontSize(14);
                    pdf.setFont('helvetica', 'normal');
                    pdf.text('Reporte de Producción', pdfWidth - margin, 18, { align: 'right' });
                    pdf.setDrawColor(0);
                    pdf.line(margin, 25, pdfWidth - margin, 25);
                    yPos = 35;
                }

                function addFooter() {
                    const pageStr = `Página ${page}`;
                    pdf.setFontSize(9);
                    pdf.text(pageStr, pdfWidth / 2, pdfHeight - 10, { align: 'center' });
                }

                addHeader();
                addFooter();

                const chartOrder = ['ordenes', 'composicion', 'topInsumos', 'produccionTiempo'];

                for (const key of chartOrder) {
                    const chartData = charts[key];
                    if (chartData && chartData.chart && chartData.description) {
                        const chartHeight = 80;
                        const contentHeight = chartHeight + 30;

                        if (yPos + contentHeight > pdfHeight - margin) {
                            pdf.addPage();
                            page++;
                            addHeader();
                            addFooter();
                            yPos = 35;
                        }

                        pdf.setFontSize(14);
                        pdf.setFont('helvetica', 'bold');
                        pdf.text(chartData.title, margin, yPos);
                        
                        pdf.setFontSize(10);
                        pdf.setFont('helvetica', 'normal');
                        const splitDescription = pdf.splitTextToSize(chartData.description, pdfWidth - (margin * 2));
                        pdf.text(splitDescription, margin, yPos + 7);
                        
                        const imgData = chartData.chart.getDataURL({
                            pixelRatio: 3,
                            backgroundColor: '#fff'
                        });
                        
                        const imgProps = pdf.getImageProperties(imgData);
                        const aspectRatio = imgProps.height / imgProps.width;
                        const finalWidth = pdfWidth - (margin * 2);
                        const finalHeight = finalWidth * aspectRatio;
                        
                        const effectiveHeight = Math.min(finalHeight, chartHeight);

                        pdf.addImage(imgData, 'PNG', margin, yPos + 20, finalWidth, effectiveHeight);
                        yPos += effectiveHeight + 30;
                    }
                }
                
                pdf.save('reporte_produccion_frozenprod.pdf');

            } catch (error) {
                console.error("Error al generar el PDF:", error);
                alert("Hubo un error al generar el PDF.");
            } finally {
                this.disabled = false;
                this.innerHTML = '<i class="fas fa-download fa-sm text-white-50"></i> Generar Reporte';
            }
        });
    }
});
