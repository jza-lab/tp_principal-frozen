$(document).ready(function() {
    let charts = {};
    let fullDetailData = [];
    let isInitialized = false;

    // Detectar cambio de pestaña (Compatible con BS5 y jQuery)
    // Usamos el ID del botón que activa la pestaña
    $('button[data-bs-target="#materia-prima"]').on('shown.bs.tab', function (e) {
        if (!isInitialized) {
            initializeDateFilter();
            isInitialized = true;
        }
        // Redimensionar gráfico al mostrarse
        setTimeout(() => {
            if (charts.eficienciaConsumo) charts.eficienciaConsumo.resize();
            if (charts.topInsumos) charts.topInsumos.resize();
        }, 200);
    });

    // Carga inicial de Top Insumos (independiente de fechas)
    loadTopInsumosChart();

    // --- Filtro de Fechas ---
    function initializeDateFilter() {
        const start = moment().subtract(29, 'days');
        const end = moment();

        $('#daterange-materia-prima').daterangepicker({
            startDate: start,
            endDate: end,
            opens: 'left',
            locale: { format: 'YYYY-MM-DD', applyLabel: "Aplicar", cancelLabel: "Cancelar" },
            ranges: {
               'Hoy': [moment(), moment()],
               'Últimos 7 Días': [moment().subtract(6, 'days'), moment()],
               'Este Mes': [moment().startOf('month'), moment().endOf('month')]
            }
        }, function(start, end) {
            loadEficienciaData(start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD'));
        });

        // Cargar datos iniciales
        loadEficienciaData(start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD'));
    }

    // --- Carga de Datos ---
    function loadTopInsumosChart() {
        // Simulación o llamada real si tienes el endpoint
        const container = document.getElementById('top-insumos-chart');
        if(!container) return;
        
        fetch('/reportes/api/produccion/top_insumos?top_n=5')
            .then(r => r.json())
            .then(res => {
                const chart = echarts.init(container);
                charts.topInsumos = chart;
                
                // Si no hay endpoint real aún, evita error
                if(!res.success) return; 

                const data = Object.entries(res.data || {}).sort((a,b) => a[1] - b[1]);
                const option = {
                    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                    xAxis: { type: 'value' },
                    yAxis: { type: 'category', data: data.map(i => i[0]) },
                    series: [{ type: 'bar', data: data.map(i => i[1]), itemStyle: { color: '#36b9cc' } }]
                };
                chart.setOption(option);
            })
            .catch(e => console.log("Top insumos no disponible o error:", e));
    }

    function loadEficienciaData(startDate, endDate) {
        fetch(`/reportes/api/materia-prima?fecha_inicio=${startDate}&fecha_fin=${endDate}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateEficienciaChart(data.data.data_agregada);
                    updateDetailTable(data.data.data_detalle);
                }
            })
            .catch(error => console.error('Error cargando materia prima:', error));
    }

    function updateEficienciaChart(data) {
        const container = document.getElementById('chart-eficiencia-consumo');
        if (!container) return;

        if (!charts.eficienciaConsumo) charts.eficienciaConsumo = echarts.init(container);

        const categories = data.map(item => item.producto);
        const planificado = data.map(item => item.planificado);
        const real = data.map(item => item.real);

        const option = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { data: ['Planificado', 'Real'], bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { type: 'category', data: categories },
            series: [
                { name: 'Planificado', type: 'bar', data: planificado, itemStyle: { color: '#4e73df' } },
                { name: 'Real', type: 'bar', data: real, itemStyle: { color: '#e74a3b' } }
            ]
        };
        charts.eficienciaConsumo.setOption(option);
    }

    // --- Tabla y Paginación ---
    let currentPage = 1;
    const rowsPerPage = 10;

    function updateDetailTable(detailObj) {
        fullDetailData = [];
        Object.keys(detailObj).forEach(prod => {
            detailObj[prod].forEach(op => {
                fullDetailData.push({
                    documento: op.documento_op,
                    producto: prod,
                    fecha: op.fecha_fin,
                    insumo: op.insumo_nombre || 'N/A', // Asegúrate que el backend envíe esto
                    planificado: op.consumo_planificado,
                    real: op.consumo_real,
                    eficiencia: op.consumo_planificado > 0 ? (op.consumo_real/op.consumo_planificado*100).toFixed(1) : 0
                });
            });
        });
        displayPage();
    }

    function displayPage() {
        const tbody = document.getElementById('detalle-ordenes-tbody');
        if(!tbody) return;
        tbody.innerHTML = '';
        
        const start = (currentPage - 1) * rowsPerPage;
        const pageData = fullDetailData.slice(start, start + rowsPerPage);

        if (pageData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No hay datos en este rango.</td></tr>';
            return;
        }

        pageData.forEach(row => {
            const tr = `
                <tr>
                    <td>${row.documento}</td>
                    <td>${row.producto}</td>
                    <td>${row.fecha ? moment(row.fecha).format('DD/MM/YYYY') : '-'}</td>
                    <td>${row.insumo}</td>
                    <td>${row.planificado}</td>
                    <td>${row.real}</td>
                    <td class="${row.eficiencia > 105 ? 'text-danger fw-bold' : ''}">${row.eficiencia}%</td>
                </tr>`;
            tbody.innerHTML += tr;
        });
        
        // Paginación simple
        const totalPages = Math.ceil(fullDetailData.length / rowsPerPage);
        const nav = document.getElementById('detalle-ordenes-pagination');
        if(nav) {
             let html = '<ul class="pagination justify-content-center">';
             html += `<li class="page-item ${currentPage===1?'disabled':''}"><a class="page-link" href="#" onclick="changePage(-1)">Anterior</a></li>`;
             html += `<li class="page-item disabled"><span class="page-link">Página ${currentPage} de ${totalPages || 1}</span></li>`;
             html += `<li class="page-item ${currentPage===totalPages?'disabled':''}"><a class="page-link" href="#" onclick="changePage(1)">Siguiente</a></li>`;
             html += '</ul>';
             nav.innerHTML = html;
        }
    }
    
    // Función global para onclick en paginación
    window.changePage = function(delta) {
        const totalPages = Math.ceil(fullDetailData.length / rowsPerPage);
        const newPage = currentPage + delta;
        if(newPage >= 1 && newPage <= totalPages) {
            currentPage = newPage;
            displayPage();
        }
    };
});