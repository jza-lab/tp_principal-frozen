document.addEventListener('DOMContentLoaded', function () {
    // --- ELEMENTOS DEL DOM ---
    const filtroCodigoInput = document.getElementById('filtroCodigo');
    const quickDateFilters = document.getElementById('quick-date-filters');
    const statusFiltersContainer = document.getElementById('status-filters');
    const ordenesList = document.getElementById('ordenes-produccion-list');
    const ordenesCountElement = document.getElementById('ordenes-count');
    const noResultsMessage = document.getElementById('no-results-message');

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
        generarFiltrosDeEstado();
        cargarFiltros();
        aplicarFiltrosYRenderizar();
        setupEventListeners();
    }

    // --- PARSEO DE DATOS ---
    function parseOrdenesFromDOM() {
        ordenes = Array.from(ordenesList.querySelectorAll('.col-md-4')).map(cardElement => {
            const codigoElement = cardElement.querySelector('code');
            const fechaPlanificadaElement = cardElement.querySelector('.text-primary i.bi-play-circle-fill');
            
            let fechaPlanificada = null;
            if (fechaPlanificadaElement) {
                const fechaText = fechaPlanificadaElement.parentElement.textContent.replace('Inicia:', '').trim();
                // Asumimos formato YYYY-MM-DD
                fechaPlanificada = new Date(fechaText + 'T00:00:00'); 
            }

            return {
                element: cardElement,
                codigo: codigoElement ? codigoElement.textContent.toLowerCase() : '',
                estado: cardElement.dataset.estado,
                fecha_planificada: fechaPlanificada
            };
        });
    }

    // --- GENERACIÓN DINÁMICA DE FILTROS ---
    function generarFiltrosDeEstado() {
        const estados = new Set(ordenes.map(p => p.estado));
        const estadosOrdenados = ["Todas", "Pendientes", "En Espera", "Listas Prod.", "L1", "L2", "Calidad", "Completadas", "Consolidadas", "Canceladas"];
        
        const Mapeo_Estados = {
            "Todas": "TODAS",
            "Pendientes": "PENDIENTE",
            "En Espera": "EN ESPERA",
            "Listas Prod.": "LISTA PARA PRODUCIR",
            "L1": "EN_LINEA_1",
            "L2": "EN_LINEA_2",
            "Calidad": "CONTROL_DE_CALIDAD",
            "Completadas": "COMPLETADA",
            "Consolidadas": "CONSOLIDADA",
            "Canceladas": "CANCELADA"
        };
        
        statusFiltersContainer.innerHTML = '';
        
        estadosOrdenados.forEach(estadoNombre => {
            const estadoKey = Mapeo_Estados[estadoNombre];
            if (estadoKey === "TODAS" || estados.has(estadoKey)) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'btn btn-sm status-filter-btn';
                button.textContent = estadoNombre;
                button.dataset.estado = estadoKey;
                statusFiltersContainer.appendChild(button);
            }
        });
    }

    // --- MANEJO DE ESTADO DE FILTROS ---
    function guardarFiltros() {
        localStorage.setItem('filtrosOrdenesProduccion', JSON.stringify(filtros));
    }

    function cargarFiltros() {
        const filtrosGuardados = localStorage.getItem('filtrosOrdenesProduccion');
        if (filtrosGuardados) {
            filtros = JSON.parse(filtrosGuardados);
        }
        // Reflejar estado en la UI
        filtroCodigoInput.value = filtros.codigo;
        actualizarBotonesActivos();
    }
    
    function actualizarBotonesActivos() {
        // Botones de estado
        document.querySelectorAll('#status-filters .status-filter-btn').forEach(btn => {
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

        // 1. Filtrar por fecha (lógica de cliente)
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

        // 2. Filtrar por estado
        if (filtros.estado !== 'TODAS') {
            ordenesFiltradas = ordenesFiltradas.filter(o => o.estado === filtros.estado);
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
        ordenesCountElement.textContent = `${count} de ${ordenes.length} órdenes mostradas.`;
        noResultsMessage.style.display = count === 0 ? '' : 'none';
        
        // Guardar el estado actual de los filtros
        guardarFiltros();
    }

    // --- EVENT LISTENERS ---
    function setupEventListeners() {
        // Filtro por código
        filtroCodigoInput.addEventListener('input', () => {
            filtros.codigo = filtroCodigoInput.value.toLowerCase();
            aplicarFiltrosYRenderizar();
        });

        // Filtros de fecha
        quickDateFilters.addEventListener('click', e => {
            if (e.target.tagName === 'BUTTON') {
                filtros.rangoFecha = e.target.dataset.range;
                actualizarBotonesActivos();
                aplicarFiltrosYRenderizar();
            }
        });

        // Filtros de estado
        statusFiltersContainer.addEventListener('click', e => {
            if (e.target.classList.contains('status-filter-btn')) {
                filtros.estado = e.target.dataset.estado;
                actualizarBotonesActivos();
                aplicarFiltrosYRenderizar();
            }
        });
    }

    // --- INICIAR LA APP ---
    inicializar();
});
