document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const searchInput = document.getElementById('searchInput');
    const quickDateFilters = document.getElementById('quick-date-filters');
    const statusFiltersContainer = document.getElementById('status-filters');
    const ordenesList = document.getElementById('ordenes-produccion-list');
    const ordenesCountElement = document.getElementById('ordenes-count');
    const noResultsMessage = document.getElementById('no-results-message');
    const btnClearAll = document.getElementById('btnClearAll');

    // Almacén de datos y estado de filtros
    let ordenes = [];
    let filtros = {
        codigo: '',
        estado: 'TODAS',
        rangoFecha: 'historico' 
    };

    // --- INICIALIZACIÓN ---
    function inicializar() {
        parseOrdenesFromDOM();
        cargarFiltros();
        aplicarFiltrosYRenderizar();
        setupEventListeners();
    }

    // --- PARSEO DE DATOS ---
    function parseOrdenesFromDOM() {
        ordenes = Array.from(ordenesList.querySelectorAll('.col-md-4')).map(cardElement => {
            const fechaPlanificadaElement = cardElement.querySelector('.text-primary i.bi-play-circle-fill');
            
            let fechaPlanificada = null;
            if (fechaPlanificadaElement) {
                const fechaText = fechaPlanificadaElement.parentElement.textContent.replace('Inicia:', '').trim();
                fechaPlanificada = new Date(fechaText + 'T00:00:00'); 
            }

            return {
                element: cardElement,
                codigo: cardElement.dataset.codigo.toLowerCase(),
                estado: cardElement.dataset.estado,
                linea: cardElement.dataset.linea,
                fecha_planificada: fechaPlanificada
            };
        });
    }

    // --- MANEJO DE ESTADO DE FILTROS ---
    function guardarFiltros() {
        sessionStorage.setItem('filtrosOrdenesProduccion', JSON.stringify(filtros));
    }

    function cargarFiltros() {
        const filtrosGuardados = sessionStorage.getItem('filtrosOrdenesProduccion');
        if (filtrosGuardados) {
            filtros = JSON.parse(filtrosGuardados);
        }
        // Reflejar estado en la UI
        searchInput.value = filtros.codigo;
        actualizarBotonesActivos();
    }
    
    function actualizarBotonesActivos() {
        // Botones de estado
        document.querySelectorAll('#status-filters .btn-filter-estado').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.estado === filtros.estado);
        });
        // Botones de fecha
        document.querySelectorAll('#quick-date-filters button').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.range === filtros.rangoFecha);
        });
    }

    // --- LÓGICA DE FILTRADO Y RENDERIZADO ---
    function aplicarFiltrosYRenderizar() {
        let ordenesFiltradas = [...ordenes];

        // 1. Filtrar por fecha
        if (filtros.rangoFecha !== 'historico') {
            const hoy = new Date();
            hoy.setHours(0, 0, 0, 0);
            let inicio;

            if (filtros.rangoFecha === 'hoy') {
                inicio = hoy;
            } else if (filtros.rangoFecha === 'semana') {
                inicio = new Date(hoy);
                inicio.setDate(hoy.getDate() - hoy.getDay());
            } else if (filtros.rangoFecha === 'mes') {
                inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
            }
            
            if (inicio) {
                ordenesFiltradas = ordenesFiltradas.filter(o => o.fecha_planificada && o.fecha_planificada >= inicio);
            }
        }

        // 2. Filtrar por estado o línea
        if (filtros.estado !== 'TODAS') {
            if (filtros.estado === 'linea_1' || filtros.estado === 'linea_2') {
                const lineaNum = filtros.estado.split('_')[1];
                ordenesFiltradas = ordenesFiltradas.filter(o => o.linea === lineaNum);
            } else {
                ordenesFiltradas = ordenesFiltradas.filter(o => o.estado === filtros.estado);
            }
        }

        // 3. Filtrar por código
        if (filtros.codigo) {
            ordenesFiltradas = ordenesFiltradas.filter(o => o.codigo.includes(filtros.codigo));
        }

        // Renderizar
        let count = 0;
        ordenes.forEach(orden => {
            const debeMostrarse = ordenesFiltradas.some(p => p.element === orden.element);
            orden.element.style.display = debeMostrarse ? '' : 'none';
            if (debeMostrarse) {
                count++;
            }
        });
        
        // Actualizar UI
        ordenesCountElement.innerHTML = `<strong>${count}</strong> de ${ordenes.length} órdenes`;
        noResultsMessage.style.display = count === 0 ? '' : 'none';
        
        // Botón limpiar
        const hayFiltrosActivos = filtros.codigo !== '' || filtros.estado !== 'TODAS' || filtros.rangoFecha !== 'historico';
        btnClearAll.style.display = hayFiltrosActivos ? 'block' : 'none';

        guardarFiltros();
    }

    // --- EVENT LISTENERS ---
    function setupEventListeners() {
        // Filtro por código
        searchInput.addEventListener('input', () => {
            filtros.codigo = searchInput.value.toLowerCase();
            aplicarFiltrosYRenderizar();
        });

        // Filtros de fecha
        quickDateFilters.addEventListener('click', e => {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                const button = e.target.tagName === 'BUTTON' ? e.target : e.target.closest('button');
                filtros.rangoFecha = button.dataset.range;
                actualizarBotonesActivos();
                aplicarFiltrosYRenderizar();
            }
        });

        // Filtros de estado
        statusFiltersContainer.addEventListener('click', e => {
            if (e.target.classList.contains('btn-filter-estado') || e.target.closest('.btn-filter-estado')) {
                 const button = e.target.classList.contains('btn-filter-estado') ? e.target : e.target.closest('.btn-filter-estado');
                filtros.estado = button.dataset.estado;
                actualizarBotonesActivos();
                aplicarFiltrosYRenderizar();
            }
        });

        // Limpiar filtros
        btnClearAll.addEventListener('click', () => {
            filtros = { codigo: '', estado: 'TODAS', rangoFecha: 'historico' };
            searchInput.value = '';
            actualizarBotonesActivos();
            aplicarFiltrosYRenderizar();
        });
    }

    // --- INICIAR LA APP ---
    inicializar();
});
