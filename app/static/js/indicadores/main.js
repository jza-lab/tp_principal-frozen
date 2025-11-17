// Definir las funciones de actualización en el alcance global para que puedan ser llamadas
// a través de diferentes archivos. Las funciones en sí mismas serán definidas en
// sus respectivos archivos (ventas.js, finanzas.js, etc.).
var updateTopProductosChart, updateFacturacionChart, updateRentabilidadChart, 
    updateCostoGananciaChart, updateDescomposicionCostosChart, updateTopClientesChart, 
    updateParetoChart, updateAntiguedadInsumosChart, updateAntiguedadProductosChart;

document.addEventListener('DOMContentLoaded', function () {
    console.log("Indicadores Main Script Loaded");

    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Función central para actualizar todos los gráficos
    const updateAllCharts = () => {
        console.log("Updating all charts...");
        if (typeof updateTopProductosChart === 'function') updateTopProductosChart();
        if (typeof updateFacturacionChart === 'function') updateFacturacionChart();
        if (typeof updateRentabilidadChart === 'function') updateRentabilidadChart();
        if (typeof updateCostoGananciaChart === 'function') updateCostoGananciaChart();
        if (typeof updateDescomposicionCostosChart === 'function') updateDescomposicionCostosChart();
        if (typeof updateTopClientesChart === 'function') updateTopClientesChart();
        if (typeof updateParetoChart === 'function') updateParetoChart();
        
        // Estos no dependen del filtro de fecha, pero los llamamos por consistencia
        if (typeof updateAntiguedadInsumosChart === 'function') updateAntiguedadInsumosChart();
        if (typeof updateAntiguedadProductosChart === 'function') updateAntiguedadProductosChart();
    };

    // Manejador para el botón de filtro principal
    const filterButton = document.querySelector('form button[type="submit"]');
    if (filterButton) {
        filterButton.addEventListener('click', (e) => {
            e.preventDefault(); // Prevenir la recarga de la página
            console.log("Filter button clicked.");
            updateAllCharts();
        });
    } else {
        console.error("Filter button not found.");
    }
    
    // Carga inicial de todos los gráficos
    console.log("Initial chart load.");
    // Llamar a updateAllCharts() después de un breve retraso para asegurar que la primera pestaña esté visible
    setTimeout(updateAllCharts, 100);

    // Listener para cuando se muestra una nueva pestaña
    document.querySelectorAll('#kpiTab button[data-bs-toggle="tab"]').forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', event => {
            console.log(`Tab shown: ${event.target.id}`);
            // Redimensionar el gráfico dentro de la pestaña activa
            const targetPaneId = event.target.getAttribute('data-bs-target');
            const chartDom = document.querySelector(`${targetPaneId} div[id$='-chart']`);
            if (chartDom) {
                const chart = echarts.getInstanceByDom(chartDom);
                if (chart) {
                    console.log(`Resizing chart in ${targetPaneId}`);
                    chart.resize();
                }
            }
        });
    });

    // Redimensionar todos los gráficos al cambiar el tamaño de la ventana
    window.addEventListener('resize', function() {
        // Usamos una función para evitar errores si un gráfico no está en la página
        const resizeChart = (id) => {
            const chartDom = document.getElementById(id);
            if(chartDom) {
                const instance = echarts.getInstanceByDom(chartDom);
                if(instance) {
                    instance.resize();
                }
            }
        };

        resizeChart('top-productos-chart');
        resizeChart('facturacion-chart');
        resizeChart('rentabilidad-productos-chart');
        resizeChart('costo-ganancia-chart');
        resizeChart('descomposicion-costos-chart');
        resizeChart('top-clientes-chart');
        resizeChart('pareto-desperdicio-chart');
        resizeChart('antiguedad-insumos-chart');
        resizeChart('antiguedad-productos-chart');
    });
});
