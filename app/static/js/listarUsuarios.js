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

    let currentFilter = 'all';

    // --- FUNCIONES DE RENDERIZADO ---
    function createTotemActivityCard(sesion) {
        const user = sesion.usuario;
        const loginTime = new Date(sesion.fecha_inicio + 'Z').toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        const logoutTime = sesion.fecha_fin ? new Date(sesion.fecha_fin + 'Z').toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) : null;

        const statusClass = logoutTime ? 'status-exit' : 'status-enter';
        const statusIcon = logoutTime ? 'box-arrow-left' : 'box-arrow-in-right';
        const statusText = logoutTime ? `Egreso ${logoutTime}` : `Ingreso ${loginTime}`;
        
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
                    </div>
                </div>
                <div class="activity-card-status ${statusClass}">
                    <i class="bi bi-${statusIcon}"></i>
                    <span>${statusText}</span>
                </div>
            </div>`;
    }

    function createWebActivityCard(user) {
        const loginTime = new Date(user.ultimo_login_web + 'Z').toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
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
                    </div>
                </div>
                <div class="activity-card-status status-online">
                    <i class="bi bi-clock-history"></i>
                    <span>Último login ${loginTime}</span>
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
                    result.data.forEach((item, index) => {
                        setTimeout(() => {
                            container.innerHTML += cardFn(item);
                        }, index * 50);
                    });
                    updateCounter(counterEl, result.data.length);
                } else {
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

    // Cargar datos de actividad
    fetchAndRender(URL_TOTEM_ACTIVITY, totemContainer, loadingTotem, noTotemMsg, createTotemActivityCard, totemCounter);
    fetchAndRender(URL_WEB_ACTIVITY, webContainer, loadingWeb, noWebMsg, createWebActivityCard, webCounter);

    // --- LÓGICA DE BÚSQUEDA Y FILTROS ---
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

    // Event listeners para búsqueda
    searchInput.addEventListener('input', filterAndSearch);
    
    clearSearchBtn.addEventListener('click', function() {
        searchInput.value = '';
        filterAndSearch();
        searchInput.focus();
    });

    // Event listeners para filtros
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            filterButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilter = this.dataset.filter;
            filterAndSearch();
        });
    });

    // Inicializar contadores
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