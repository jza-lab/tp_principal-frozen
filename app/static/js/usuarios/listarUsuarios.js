document.addEventListener('DOMContentLoaded', function() {
    // --- ELEMENTOS DEL DOM ---
    const totemContainer = document.getElementById('totem-activity-container');
    const loadingTotem = document.getElementById('loading-totem-activity');
    const noTotemMsg = document.getElementById('no-totem-activity');
    const totemCounter = document.getElementById('totem-counter');

    const webContainer = document.getElementById('web-activity-container');
    const loadingWeb = document.getElementById('loading-web-activity');
    const noWebMsg = document.getElementById('no-web-activity');
    const webCounter = document.getElementById('web-counter');

    const searchInput = document.getElementById('user-search-input');
    const clearSearchBtn = document.getElementById('clear-search');
    const allUsersContainer = document.getElementById('all-users-container');
    const userCards = allUsersContainer.querySelectorAll('.user-card-wrapper');
    const noSearchResults = document.getElementById('no-search-results');
    const filterButtons = document.querySelectorAll('.filter-btn');

    // Elementos para filtros de actividad
    const filterSector = document.getElementById('filter-sector');
    const filterFechaDesde = document.getElementById('filter-fecha-desde');
    const filterFechaHasta = document.getElementById('filter-fecha-hasta');
    const applyFiltersBtn = document.getElementById('apply-filters');

    let currentFilter = 'all';

    // --- FUNCIONES DE RENDERIZADO ---
    function createTotemActivityCard(sesion) {
        const user = sesion.usuario;
        const loginDate = new Date(sesion.fecha_inicio + 'Z');
        const formattedDate = loginDate.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const loginTime = loginDate.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        const logoutTime = sesion.fecha_fin ? new Date(sesion.fecha_fin + 'Z').toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) : null;

        const statusClass = logoutTime ? 'status-exit' : 'status-enter';
        const statusIcon = logoutTime ? 'box-arrow-left' : 'box-arrow-in-right';
        const statusText = logoutTime ? `Egreso ${logoutTime}` : `Ingreso ${loginTime}`;
        
        const sector = user.sectores && user.sectores.length > 0 && user.sectores[0].sectores ? user.sectores[0].sectores.nombre : 'Sin sector';

        return `
            <div class="activity-card fade-in">
                <div class="activity-card-avatar">
                    <i class="bi bi-person-circle"></i>
                </div>
                <div class="activity-card-body">
                    <div class="activity-card-title">${user.nombre} ${user.apellido}</div>
                    <div class="activity-card-details">
                        <span><i class="bi bi-hash"></i>${user.legajo || 'N/A'}</span>
                        <span><i class="bi bi-shield-check"></i>${user.roles ? user.roles.nombre : 'Sin rol'}</span>
                        <span><i class="bi bi-briefcase"></i>${sector}</span>
                        <span><i class="bi bi-calendar-event"></i>${formattedDate}</span>
                    </div>
                </div>
                <div class="activity-card-status ${statusClass}">
                    <i class="bi bi-${statusIcon}"></i>
                    <span>${statusText}</span>
                </div>
            </div>`;
    }

    function createWebActivityCard(user) {
        let formattedDate = 'Sin registro';
        let loginTimeText = 'Sin registro de login';

        if (user.ultimo_login_web) {
            const loginDate = new Date(user.ultimo_login_web + 'Z');
            if (!isNaN(loginDate.getTime())) {
                formattedDate = loginDate.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
                const loginTime = loginDate.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
                loginTimeText = `Último login ${loginTime}`;
            }
        }
        
        const sector = user.sectores && user.sectores.length > 0 && user.sectores[0].sectores ? user.sectores[0].sectores.nombre : 'Sin sector';

        return `
            <div class="activity-card fade-in">
                <div class="activity-card-avatar">
                    <i class="bi bi-person-circle"></i>
                </div>
                <div class="activity-card-body">
                    <div class="activity-card-title">${user.nombre} ${user.apellido}</div>
                    <div class="activity-card-details">
                        <span><i class="bi bi-hash"></i>${user.legajo || 'N/A'}</span>
                        <span><i class="bi bi-shield-check"></i>${user.roles ? user.roles.nombre : 'Sin rol'}</span>
                        <span><i class="bi bi-briefcase"></i>${sector}</span>
                        <span><i class="bi bi-calendar-event"></i>${formattedDate}</span>
                    </div>
                </div>
                <div class="activity-card-status status-online">
                    <i class="bi bi-clock-history"></i>
                    <span>${loginTimeText}</span>
                </div>
            </div>`;
    }

    function updateCounter(counterEl, count, isActive = true) {
        const numberEl = counterEl.querySelector('.counter-number');
        numberEl.textContent = count;
        if (isActive) {
            counterEl.classList.add('active');
        }
    }
    
    // --- LÓGICA DE FETCH Y FILTRADO ---
    function fetchAndRender(url, container, loadingEl, notFoundEl, cardFn, counterEl) {
        fetch(url)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                loadingEl.style.display = 'none';
                if (result.success && result.data.length > 0) {
                    container.innerHTML = '';
                    notFoundEl.style.display = 'none';
                    result.data.forEach((item, index) => {
                        setTimeout(() => {
                            container.innerHTML += cardFn(item);
                        }, index * 50);
                    });
                    updateCounter(counterEl, result.data.length);
                } else {
                    container.innerHTML = '';
                    notFoundEl.style.display = 'flex';
                    updateCounter(counterEl, 0, false);
                }
            })
            .catch(error => {
                console.error(`Error en fetch para ${url}:`, error);
                loadingEl.style.display = 'none';
                container.innerHTML = `<div class="text-center text-danger py-3"><p>No se pudo cargar la actividad.</p></div>`;
            });
    }
    
    function applyActivityFilters() {
        // Mostrar spinners y limpiar contenido actual
        loadingTotem.style.display = 'block';
        loadingWeb.style.display = 'block';
        totemContainer.innerHTML = '';
        webContainer.innerHTML = '';
        noTotemMsg.style.display = 'none';
        noWebMsg.style.display = 'none';

        // Obtener valores de los filtros
        const sectorId = filterSector.value;
        const fechaDesde = filterFechaDesde.value;
        const fechaHasta = filterFechaHasta.value;

        // Construir la query string
        const params = new URLSearchParams();
        if (sectorId) params.append('sector_id', sectorId);
        if (fechaDesde) params.append('fecha_desde', fechaDesde);
        if (fechaHasta) params.append('fecha_hasta', fechaHasta);
        const queryString = params.toString();

        // Construir las URLs finales
        const totemUrl = `${URL_TOTEM_ACTIVITY}?${queryString}`;
        const webUrl = `${URL_WEB_ACTIVITY}?${queryString}`;

        // Realizar la búsqueda con los nuevos filtros
        fetchAndRender(totemUrl, totemContainer, loadingTotem, noTotemMsg, createTotemActivityCard, totemCounter);
        fetchAndRender(webUrl, webContainer, loadingWeb, noWebMsg, createWebActivityCard, webCounter);
    }
    
    // Cargar datos iniciales de actividad (hoy por defecto)
    applyActivityFilters();

    // --- LÓGICA DE BÚSQUEDA Y FILTROS DE USUARIOS ---
    function updateUserCounts() {
        const all = userCards.length;
        let active = 0;
        let inactive = 0;
        
        userCards.forEach(card => {
            if (card.dataset.status === 'active') active++;
            else inactive++;
        });
        
        document.getElementById('count-all').textContent = all;
        document.getElementById('count-active').textContent = active;
        document.getElementById('count-inactive').textContent = inactive;
    }

    function filterAndSearch() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        let visibleCount = 0;

        userCards.forEach(card => {
            const legajo = card.dataset.legajo.toLowerCase();
            const nombre = card.dataset.nombre.toLowerCase();
            const status = card.dataset.status;

            const matchesSearch = legajo.includes(searchTerm) || nombre.includes(searchTerm);
            const matchesFilter = currentFilter === 'all' || status === currentFilter;

            if (matchesSearch && matchesFilter) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // Mostrar mensaje de sin resultados
        if (visibleCount === 0 && searchTerm) {
            noSearchResults.style.display = 'flex';
            allUsersContainer.style.display = 'none';
        } else {
            noSearchResults.style.display = 'none';
            allUsersContainer.style.display = 'flex';
        }

        // Mostrar/ocultar botón de limpiar búsqueda
        clearSearchBtn.style.display = searchTerm ? 'flex' : 'none';
    }

    // --- EVENT LISTENERS ---
    // Búsqueda de usuarios
    searchInput.addEventListener('input', filterAndSearch);
    
    clearSearchBtn.addEventListener('click', function() {
        searchInput.value = '';
        filterAndSearch();
        searchInput.focus();
    });

    // Filtros de estado de usuarios
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            filterButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilter = this.dataset.filter;
            filterAndSearch();
        });
    });
    
    // --- LÓGICA DE VALIDACIÓN DE FECHAS ---
    function setupDateFilters() {
        const fechaDesdeInput = filterFechaDesde;
        const fechaHastaInput = filterFechaHasta;

        fechaDesdeInput.addEventListener('change', () => {
            // Si se elige una fecha "desde" posterior a la "hasta", se resetea la "hasta"
            if (fechaHastaInput.value && fechaDesdeInput.value > fechaHastaInput.value) {
                fechaHastaInput.value = '';
            }
            // La fecha "hasta" no puede ser anterior a la "desde"
            fechaHastaInput.min = fechaDesdeInput.value;
            applyActivityFilters();
        });

        fechaHastaInput.addEventListener('change', () => {
             // Si se elige una fecha "hasta" anterior a la "desde", se resetea la "desde"
            if (fechaDesdeInput.value && fechaHastaInput.value < fechaDesdeInput.value) {
                fechaDesdeInput.value = '';
            }
            applyActivityFilters();
        });
    }
    
    // Filtros de actividad
    filterSector.addEventListener('input', applyActivityFilters);
    setupDateFilters();

    // --- INICIALIZACIÓN ---
    updateUserCounts();

    // Animación de entrada para las tarjetas al cambiar de pestaña
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const targetPane = document.querySelector(e.target.dataset.bsTarget);
            targetPane.classList.add('tab-fade-in');
            setTimeout(() => {
                targetPane.classList.remove('tab-fade-in');
            }, 400);
        });
    });
});
