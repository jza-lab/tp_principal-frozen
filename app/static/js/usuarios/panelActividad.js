const ActividadPanel = (function() {
    // --- ELEMENTOS DEL DOM (privados) ---
    let totemContainer, loadingTotem, noTotemMsg, totemCounter;
    let webContainer, loadingWeb, noWebMsg, webCounter;
    let filterSector, filterFechaDesde, filterFechaHasta;

    // --- FUNCIONES DE RENDERIZADO (privadas) ---
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
                <div class="activity-card-avatar"><i class="bi bi-person-circle"></i></div>
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
                <div class="activity-card-avatar"><i class="bi bi-person-circle"></i></div>
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
        counterEl.querySelector('.counter-number').textContent = count;
        counterEl.classList.toggle('active', isActive);
    }

    // --- LÓGICA DE FETCH Y FILTRADO (privada) ---
    function fetchAndRender(url, container, loadingEl, notFoundEl, cardFn, counterEl) {
        loadingEl.style.display = 'block';
        container.innerHTML = '';
        notFoundEl.style.display = 'none';

        fetch(url)
            .then(response => response.ok ? response.json() : Promise.reject('Error de red'))
            .then(result => {
                if (result.success && result.data.length > 0) {
                    container.innerHTML = result.data.map(cardFn).join('');
                    updateCounter(counterEl, result.data.length);
                } else {
                    notFoundEl.style.display = 'flex';
                    updateCounter(counterEl, 0, false);
                }
            })
            .catch(error => {
                console.error(`Error en fetch para ${url}:`, error);
                container.innerHTML = `<div class="text-center text-danger py-3"><p>No se pudo cargar la actividad.</p></div>`;
            })
            .finally(() => {
                loadingEl.style.display = 'none';
            });
    }
    
    function applyActivityFilters() {
        const params = new URLSearchParams();
        if (filterSector.value) params.append('sector_id', filterSector.value);
        if (filterFechaDesde.value) params.append('fecha_desde', filterFechaDesde.value);
        if (filterFechaHasta.value) params.append('fecha_hasta', filterFechaHasta.value);
        const queryString = params.toString();

        fetchAndRender(`${URL_TOTEM_ACTIVITY}?${queryString}`, totemContainer, loadingTotem, noTotemMsg, createTotemActivityCard, totemCounter);
        fetchAndRender(`${URL_WEB_ACTIVITY}?${queryString}`, webContainer, loadingWeb, noWebMsg, createWebActivityCard, webCounter);
    }

    function setupDateFilters() {
        filterFechaDesde.addEventListener('change', () => {
            if (filterFechaHasta.value && filterFechaDesde.value > filterFechaHasta.value) {
                filterFechaHasta.value = '';
            }
            filterFechaHasta.min = filterFechaDesde.value;
            applyActivityFilters();
        });

        filterFechaHasta.addEventListener('change', () => {
            if (filterFechaDesde.value && filterFechaHasta.value < filterFechaDesde.value) {
                filterFechaDesde.value = '';
            }
            applyActivityFilters();
        });
    }

    function bindEvents() {
        filterSector.addEventListener('input', applyActivityFilters);
        setupDateFilters();
    }

    // --- MÉTODO PÚBLICO ---
    function init() {
        // Cachear elementos del DOM
        totemContainer = document.getElementById('totem-activity-container');
        loadingTotem = document.getElementById('loading-totem-activity');
        noTotemMsg = document.getElementById('no-totem-activity');
        totemCounter = document.getElementById('totem-counter');

        webContainer = document.getElementById('web-activity-container');
        loadingWeb = document.getElementById('loading-web-activity');
        noWebMsg = document.getElementById('no-web-activity');
        webCounter = document.getElementById('web-counter');

        filterSector = document.getElementById('filter-sector');
        filterFechaDesde = document.getElementById('filter-fecha-desde');
        filterFechaHasta = document.getElementById('filter-fecha-hasta');

        if (!totemContainer) return; // Salir si el panel no está presente

        // Inicializar
        applyActivityFilters(); // Cargar datos iniciales
        bindEvents();
        console.log("Panel de Actividad inicializado.");
    }

    return {
        init: init
    };
})();