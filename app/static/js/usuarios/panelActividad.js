const ActividadPanel = (function() {
    // --- ELEMENTOS DEL DOM (privados) ---
    let unifiedContainer, loadingUnified, noUnifiedMsg, activityTable, activityTableBody;
    let filterSector, filterRol, filterFechaDesde, filterFechaHasta, refreshButton;

    // --- FUNCIONES DE RENDERIZADO (privadas) ---
    function formatArgentinianDate(dateString) {
        if (!dateString) return 'N/A';
        
        try {
            // Se asegura que el string de fecha sea tratado como UTC.
            // Si no termina con 'Z', se lo agregamos.
            const utcDateString = dateString.endsWith('Z') ? dateString : dateString + 'Z';
            const date = new Date(utcDateString);

            // Verificar si la fecha es válida
            if (isNaN(date.getTime())) {
                return 'Fecha Inválida';
            }

            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0'); // Meses son 0-indexados
            const year = date.getFullYear();
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');

            return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
        } catch (error) {
            console.error('Error al formatear fecha:', dateString, error);
            return 'Fecha Inválida';
        }
    }
    
    function createActivityTableRow(actividad) {
        const fechaIngreso = formatArgentinianDate(actividad.fecha_ingreso);
        const fechaEgreso = formatArgentinianDate(actividad.fecha_egreso);

        return `
            <tr>
                <td>${actividad.legajo}</td>
                <td>${actividad.nombre}</td>
                <td>${actividad.rol}</td>
                <td>${actividad.sector}</td>
                <td>${fechaIngreso}</td>
                <td>${fechaEgreso}</td>
                <td>${actividad.acceso_en}</td>
                <td>${actividad.metodo_acceso}</td>
                <td>${actividad.estado}</td>
                <td>
                    <a href="/admin/usuarios/${actividad.id_empleado}" class="btn btn-sm btn-outline-primary">
                        <i class="bi bi-eye"></i>
                    </a>
                </td>
            </tr>`;
    }

    // --- LÓGICA DE FETCH Y FILTRADO (privada) ---
    function fetchAndRender() {
        const params = new URLSearchParams();
        if (filterSector.value) params.append('sector_id', filterSector.value);
        if (filterRol.value) params.append('rol_id', filterRol.value);
        if (filterFechaDesde.value) params.append('fecha_desde', filterFechaDesde.value);
        if (filterFechaHasta.value) params.append('fecha_hasta', filterFechaHasta.value);
        const queryString = params.toString();

        loadingUnified.style.display = 'block';
        activityTable.style.display = 'none';
        noUnifiedMsg.style.display = 'none';

        fetch(`${URL_UNIFIED_ACTIVITY}?${queryString}`)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                if (result.success && result.data.length > 0) {
                    activityTableBody.innerHTML = result.data.map(createActivityTableRow).join('');
                    activityTable.style.display = 'table';
                } else {
                    noUnifiedMsg.style.display = 'flex';
                }
            })
            .catch(error => {
                console.error(`Error en fetch para ${URL_UNIFIED_ACTIVITY}:`, error);
                unifiedContainer.innerHTML = `<div class="text-center text-danger py-3"><p>No se pudo cargar la actividad.</p></div>`;
            })
            .finally(() => {
                loadingUnified.style.display = 'none';
            });
    }
    
    function setupDateFilters() {
        filterFechaDesde.addEventListener('change', () => {
            if (filterFechaDesde.value) {
                filterFechaHasta.min = filterFechaDesde.value;
            }
        });
    }

    function bindEvents() {
        filterSector.addEventListener('change', fetchAndRender);
        filterRol.addEventListener('change', fetchAndRender);
        filterFechaDesde.addEventListener('change', fetchAndRender);
        filterFechaHasta.addEventListener('change', fetchAndRender);
        refreshButton.addEventListener('click', fetchAndRender);
        setupDateFilters();
    }

    // --- MÉTODO PÚBLICO ---
    function init() {
        // Cachear elementos del DOM
        unifiedContainer = document.getElementById('unified-activity-container');
        loadingUnified = document.getElementById('loading-unified-activity');
        noUnifiedMsg = document.getElementById('no-unified-activity');
        activityTable = document.getElementById('activity-table');
        activityTableBody = document.getElementById('activity-table-body');

        filterSector = document.getElementById('filter-sector');
        filterRol = document.getElementById('filter-rol');
        filterFechaDesde = document.getElementById('filter-fecha-desde');
        filterFechaHasta = document.getElementById('filter-fecha-hasta');
        refreshButton = document.getElementById('refresh-activity');

        if (!unifiedContainer) return; // Salir si el panel no está presente

        // Inicializar
        fetchAndRender(); // Cargar datos iniciales
        bindEvents();
        console.log("Panel de Actividad Unificada inicializado.");
    }

    return {
        init: init
    };
})();
