const clientesColors = ['#9A60B4', '#EA7CCC', '#5470C6', '#91CC75', '#EE6666'];

updateTopClientesChart = () => {
    const chartDom = document.getElementById('top-clientes-chart');
    if (!chartDom) return;

    const chart = echarts.getInstanceByDom(chartDom) || echarts.init(chartDom);
    const topNSelector = document.getElementById('top-n-cliente-selector');
    const criterioSelector = document.getElementById('criterio-cliente-selector');
    const downloadBtn = document.getElementById('download-top-clientes');

    const topN = topNSelector.value;
    const criterio = criterioSelector.value;
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    
    chart.showLoading();
    fetch(`/reportes/api/clientes/top_clientes?top_n=${topN}&criterio=${criterio}&fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`)
        .then(response => response.json())
        .then(data => {
            chart.hideLoading();
            if (data.error || data.labels.length === 0) {
                chart.setOption({ title: { text: 'No se encontraron datos', left: 'center', top: 'center' }, series: [] }, true);
                document.getElementById('top-clientes-descripcion').textContent = 'No se encontraron datos de clientes para este período.';
                return;
            }

            const chartData = data.labels.map((label, i) => ({ name: label, value: data.data[i] }));

            const option = {
                tooltip: { trigger: 'item', formatter: '{b}: {c}' + (criterio === 'valor' ? '$' : ' pedidos') },
                legend: { orient: 'vertical', left: 'left', data: data.labels },
                series: [{
                    name: 'Top Clientes', type: 'pie', radius: '75%', center: ['65%', '50%'], data: chartData,
                    emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
                    color: clientesColors
                }]
            };
            chart.setOption(option, true);
            
            const descripcionEl = document.getElementById('top-clientes-descripcion');
            const topCliente = chartData[0];
            const unidad = criterio === 'valor' ? `$${topCliente.value.toFixed(2)}` : `${topCliente.value} pedidos`;
            descripcionEl.textContent = `El cliente principal en este período es "${topCliente.name}" con un total de ${unidad}.`;
        });
        
    if (topNSelector && !topNSelector.hasAttribute('data-initialized')) {
        topNSelector.addEventListener('change', updateTopClientesChart);
        topNSelector.setAttribute('data-initialized', 'true');
    }
    if(criterioSelector && !criterioSelector.hasAttribute('data-initialized')) {
        criterioSelector.addEventListener('change', updateTopClientesChart);
        criterioSelector.setAttribute('data-initialized', 'true');
    }
    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = chart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'top_clientes.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};
