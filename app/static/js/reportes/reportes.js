document.addEventListener('DOMContentLoaded', function () {
    // Estética y configuración común para los gráficos
    const chartColors = {
        primary: 'rgba(54, 162, 235, 0.6)',
        secondary: 'rgba(255, 99, 132, 0.6)',
        tertiary: 'rgba(75, 192, 192, 0.6)',
        background: 'rgba(255, 255, 255, 0.8)'
    };

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
            tooltip: {
                callbacks: {
                    label: function (context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(context.parsed.y);
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                grid: {
                    display: false
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(200, 200, 200, 0.2)'
                }
            }
        }
    };

    const chartInstances = {};

    function loadIngresosVsEgresosChart(periodo = 'semanal') {
        fetch(`/reportes/api/ingresos_vs_egresos?periodo=${periodo}`)
            .then(response => response.json())
            .then(data => {
                const ctx = document.getElementById('ingresosVsEgresosChart').getContext('2d');
                if (chartInstances.ingresosVsEgresos) {
                    chartInstances.ingresosVsEgresos.destroy();
                }
                chartInstances.ingresosVsEgresos = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: 'Ingresos',
                                data: data.ingresos,
                                borderColor: chartColors.primary,
                                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                                tension: 0.1,
                                fill: true
                            },
                            {
                                label: 'Egresos',
                                data: data.egresos,
                                borderColor: chartColors.secondary,
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                tension: 0.1,
                                fill: true
                            }
                        ]
                    },
                    options: commonOptions
                });
            });
    }

    function loadTopProductosChart() {
        fetch('/reportes/api/top_productos')
            .then(response => response.json())
            .then(data => {
                const ctx = document.getElementById('topProductosChart').getContext('2d');
                if (chartInstances.topProductos) {
                    chartInstances.topProductos.destroy();
                }
                chartInstances.topProductos = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Cantidad Vendida',
                            data: data.data,
                            backgroundColor: chartColors.tertiary,
                        }]
                    },
                    options: { ...commonOptions, indexAxis: 'y' }
                });
            });
    }

    function loadStockCriticoChart() {
        fetch('/reportes/api/stock_critico')
            .then(response => response.json())
            .then(data => {
                const ctx = document.getElementById('stockCriticoChart').getContext('2d');
                if (chartInstances.stockCritico) {
                    chartInstances.stockCritico.destroy();
                }
                chartInstances.stockCritico = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: 'Stock Actual',
                                data: data.data_actual,
                                backgroundColor: 'rgba(255, 159, 64, 0.6)'
                            },
                            {
                                label: 'Stock Mínimo',
                                data: data.data_minimo,
                                backgroundColor: 'rgba(255, 99, 132, 0.6)'
                            }
                        ]
                    },
                    options: commonOptions
                });
            });
    }

    const reportesTab = document.getElementById('reportesTab');
    const tabs = reportesTab.querySelectorAll('button[data-bs-toggle="tab"]');

    loadIngresosVsEgresosChart('semanal');
    
    document.querySelectorAll('.dropdown-item[data-periodo]').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const periodo = this.getAttribute('data-periodo');
            loadIngresosVsEgresosChart(periodo);
        });
    });

    let isFirstLoad = {
        ventas: true,
        stock: true
    };

    tabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            const targetId = event.target.getAttribute('data-bs-target');
            
            if (targetId === '#ventas' && isFirstLoad.ventas) {
                loadTopProductosChart();
                isFirstLoad.ventas = false;
            } else if (targetId === '#stock' && isFirstLoad.stock) {
                loadStockCriticoChart();
                isFirstLoad.stock = false;
            }
        });
    });
});
