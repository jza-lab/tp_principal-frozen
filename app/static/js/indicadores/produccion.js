const produccionColors = ['#EE6666', '#FAC858', '#5470C6', '#91CC75', '#73C0DE'];

updateParetoChart = () => {
    const paretoChartDom = document.getElementById('pareto-desperdicio-chart');
    if (!paretoChartDom) return;

    const paretoChart = echarts.getInstanceByDom(paretoChartDom) || echarts.init(paretoChartDom);
    const downloadBtn = document.getElementById('download-pareto-desperdicio');

    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    
    paretoChart.showLoading();
    fetch(`/reportes/api/produccion/causas_desperdicio?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`)
        .then(response => response.json())
        .then(data => {
            paretoChart.hideLoading();
            if (data.error || data.labels.length === 0) {
                paretoChart.setOption({
                    title: { text: 'No se encontraron datos', left: 'center', top: 'center' },
                    series: []
                }, true);
                console.warn(data.error || "No data for Pareto chart");
                document.getElementById('pareto-desperdicio-descripcion').textContent = 'No se registraron desperdicios en el período seleccionado.';
                return;
            }

            const option = {
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                grid: { containLabel: true },
                xAxis: [{ type: 'category', data: data.labels, axisLabel: { interval: 0, rotate: 30 } }],
                yAxis: [
                    { type: 'value', name: 'Cantidad (kg)' },
                    { type: 'value', name: 'Acumulado (%)', min: 0, max: 100, interval: 20, axisLabel: { formatter: '{value}%' } }
                ],
                series: [
                    { name: 'Desperdicio', type: 'bar', data: data.data, itemStyle: { color: produccionColors[0] } },
                    { name: 'Acumulado', type: 'line', yAxisIndex: 1, data: data.line_data, smooth: true, itemStyle: { color: produccionColors[2] } }
                ]
            };
            paretoChart.setOption(option, true);
            
            const descripcionEl = document.getElementById('pareto-desperdicio-descripcion');
            const causaPrincipal = data.labels[0];
            const porcentajeCausaPrincipal = data.line_data[0];
            descripcionEl.textContent = `La causa principal de desperdicio es "${causaPrincipal}", responsable del ${porcentajeCausaPrincipal}% del total.`;
        });

    if (downloadBtn && !downloadBtn.hasAttribute('data-initialized')) {
        downloadBtn.addEventListener('click', () => {
             const url = paretoChart.getConnectedDataURL({ pixelRatio: 2, backgroundColor: '#fff' });
             const a = document.createElement('a');
             a.href = url;
             a.download = 'pareto_desperdicios.png';
             a.click();
        });
        downloadBtn.setAttribute('data-initialized', 'true');
    }
};