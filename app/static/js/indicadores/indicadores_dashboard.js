document.addEventListener('DOMContentLoaded', function () {
    const tabElements = document.querySelectorAll('#kpiTab .nav-link');
    const dashboardState = {};
    let loadedTabs = new Set();
    let chartInstances = {};

    // --- UTILS ---

    function obtenerUrlApi(category) {
        const state = dashboardState[category] || { period: 'semana', value: '' };
        let params = [];
        if (state.value) params.push(`${state.period}=${state.value}`);

        // Añadir otros parámetros del estado (como top_n)
        Object.keys(state).forEach(key => {
            if (key !== 'period' && key !== 'value' && state[key]) {
                params.push(`${key}=${state[key]}`);
            }
        });

        return `/reportes/api/indicadores/${category}?${params.join('&')}`;
    }

    // Permite actualizar parámetros específicos del estado y recargar la pestaña
    window.updateCategoryParam = function (category, key, value) {
        if (!dashboardState[category]) dashboardState[category] = { period: 'semana', value: '' };
        dashboardState[category][key] = value;

        // Forzar recarga
        loadedTabs.delete(category);
        // Limpiar instancias de charts antiguos si es necesario (se hace en loadTabData indirectamente al limpiar HTML)

        loadTabData(category);
    }

    function showLoading(tabPane) {
        tabPane.innerHTML = `
            <div class="loading-placeholder text-center py-5">
                <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
                <p class="mt-2 text-muted small">Calculando indicadores...</p>
            </div>`;
    }

    function showError(tabPane, message) {
        tabPane.innerHTML = `
            <div class="alert alert-danger d-flex align-items-center m-3 p-2 small" role="alert">
                <i class="bi bi-exclamation-triangle-fill flex-shrink-0 me-2"></i>
                <div>${message || 'Error de carga.'}</div>
            </div>`;
    }

    // --- RENDER FUNCTIONS (COMPONENTES UI) ---

    // EXPOSE FUNCTIONS GLOBALLY
    window.createChart = function (containerId, options) {
        const chartDom = document.getElementById(containerId);
        if (!chartDom) return;
        if (chartInstances[containerId]) chartInstances[containerId].dispose();

        // Verificación especial para Gauges (que no usan 'series.data' convencional)
        const isGauge = options.series && options.series[0] && options.series[0].type === 'gauge';
        const hasData = isGauge || (options.series && options.series.some(s => s.data && s.data.length > 0));

        if (!hasData) {
            chartDom.innerHTML = `<div class="d-flex flex-column justify-content-center align-items-center h-100 text-muted opacity-50 small"><span>Sin datos</span></div>`;
            return;
        }

        const chart = echarts.init(chartDom);
        chart.setOption(options);
        chartInstances[containerId] = chart;
    }

    // Listener global para redimensionar todos los gráficos
    window.addEventListener('resize', () => {
        Object.values(chartInstances).forEach(chart => {
            if (chart) chart.resize();
        });
    });

    // TARJETA KPI MEJORADA
    window.renderKpiCard = function (title, value, subtitle, iconClass = 'bi-bar-chart-line', tooltipInfo = null, colorVariant = 'primary') {
        // Tooltip HTML construction
        const tooltipAttr = tooltipInfo
            ? `data-bs-toggle="tooltip" data-bs-placement="top" data-bs-html="true" title="${tooltipInfo}"`
            : '';

        const infoIcon = tooltipInfo
            ? `<i class="bi bi-info-circle-fill text-muted opacity-75 ms-2" style="font-size: 0.85rem; cursor: help;" ${tooltipAttr}></i>`
            : '';

        // Define background and text classes based on variant
        const bgClass = `bg-${colorVariant}-subtle`; // e.g., bg-primary-subtle
        const textClass = `text-${colorVariant}`;     // e.g., text-primary

        return `
        <div class="col-xl-3 col-md-6 mb-3">
            <div class="card stat-card h-100 border-0 shadow kpi-card position-relative overflow-hidden hover-lift bg-white">
                <!-- Subtle gradient background via inline style or class -->
                <div class="card-body p-4 position-relative z-1">
                    <div class="d-flex align-items-start justify-content-between mb-3">
                        <div>
                            <div class="d-flex align-items-center mb-2">
                                <h6 class="card-subtitle text-muted text-uppercase fw-bold tracking-wide mb-0" style="font-size: 0.75rem; letter-spacing: 0.5px;">${title}</h6>
                                ${infoIcon}
                            </div>
                            <h2 class="card-title mb-0 fw-bold text-dark display-6 gradient-text-${colorVariant}">${value}</h2>
                        </div>
                        <div class="icon-box ${bgClass} ${textClass} rounded-4 p-3 d-flex align-items-center justify-content-center shadow-sm transition-transform" style="width: 60px; height: 60px;">
                            <i class="bi ${iconClass}" style="font-size: 1.75rem;"></i>
                        </div>
                    </div>
                    <div class="d-flex align-items-center mt-auto">
                        <span class="badge bg-light text-secondary border fw-medium rounded-pill px-2 py-1 small">${subtitle}</span>
                    </div>
                </div>
            </div>
        </div>`;
    }

    window.renderChartCard = function (chartId, title, subtitle, tooltip, downloadId, chartHeight = '300px') {
        return `
            <div class="card shadow border-0 h-100 rounded-4 hover-shadow-lg transition-all bg-white">
                <div class="card-header bg-white border-bottom-0 pt-4 px-4 d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="fw-bold mb-1 text-dark h5">${title}</h6>
                        <small class="text-muted">${subtitle}</small>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-light btn-sm rounded-circle text-muted p-2 no-arrow" data-bs-toggle="dropdown" style="width: 32px; height: 32px;"><i class="bi bi-three-dots-vertical"></i></button>
                        <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0">
                            <li><button class="dropdown-item small" id="${downloadId}"><i class="bi bi-download me-2"></i>Descargar imagen</button></li>
                        </ul>
                    </div>
                </div>
                <div class="card-body px-4 pb-4 pt-2">
                    <div id="${chartId}" style="height: ${chartHeight}; width: 100%;"></div>
                </div>
            </div>`;
    }

    // NUEVO: Smart Card Component (HTML Generator)
    window.createSmartCardHTML = function (id, title, description, insight, helpText) {
        return `
        <div class="card shadow border-0 h-100 smart-card-container rounded-4 hover-shadow-lg transition-all bg-white">
            <div class="card-header bg-white d-flex justify-content-between align-items-center py-3 border-0 px-4">
                <h6 class="fw-bold text-dark mb-0 h6">${title}</h6>
                <i class="bi bi-question-circle-fill text-muted opacity-25 hover-opacity-100 transition-opacity" 
                   data-bs-toggle="tooltip" 
                   data-bs-placement="left" 
                   title="${helpText}" 
                   style="cursor: help; font-size: 1rem;"></i>
            </div>
            <div class="card-body px-4 pb-4 pt-0 d-flex flex-column h-100">
                <p class="text-muted small mb-3" style="font-size: 0.85rem;">${description}</p>
                
                <div class="flex-grow-1 position-relative" style="min-height: 280px;">
                    <div id="${id}" style="width: 100%; height: 100%; position: absolute; top: 0; left: 0;"></div>
                </div>

                <div class="alert alert-light border-0 bg-light-subtle rounded-3 mb-0 mt-3 py-2 px-3 d-flex align-items-start">
                    <i class="bi bi-lightbulb-fill text-warning me-2 mt-1"></i>
                    <span class="text-secondary small fw-medium dynamic-insight" style="line-height: 1.4;">${insight}</span>
                </div>
            </div>
        </div>`;
    }

    // Componente para tarjeta dividida (Estados + Líneas)
    window.createSplitSmartCardHTML = function (idLeft, idRight, title, description, insight, helpText) {
        return `
        <div class="card shadow border-0 h-100 smart-card-container rounded-4 hover-shadow-lg transition-all bg-white">
            <div class="card-header bg-white d-flex justify-content-between align-items-center py-3 border-0 px-4">
                <h6 class="fw-bold text-dark mb-0 h6">${title}</h6>
                <i class="bi bi-question-circle-fill text-muted opacity-25 hover-opacity-100 transition-opacity" 
                   data-bs-toggle="tooltip" 
                   data-bs-placement="left" 
                   title="${helpText}" 
                   style="cursor: help; font-size: 1rem;"></i>
            </div>
            <div class="card-body px-4 pb-4 pt-0 d-flex flex-column h-100">
                <p class="text-muted small mb-3" style="font-size: 0.85rem;">${description}</p>
                
                <div class="row g-0 flex-grow-1" style="min-height: 280px;">
                    <div class="col-6 position-relative pe-2">
                        <h6 class="text-center text-muted small fw-bold text-uppercase mb-2" style="font-size: 0.7rem; letter-spacing: 1px;">Estados</h6>
                        <div id="${idLeft}" style="width: 100%; height: calc(100% - 20px);"></div>
                    </div>
                    <div class="col-6 position-relative ps-2 border-start border-light">
                        <h6 class="text-center text-muted small fw-bold text-uppercase mb-2" style="font-size: 0.7rem; letter-spacing: 1px;">Líneas</h6>
                        <div id="${idRight}" style="width: 100%; height: calc(100% - 20px);"></div>
                    </div>
                </div>

                <div class="alert alert-light border-0 bg-light-subtle rounded-3 mb-0 mt-3 py-2 px-3 d-flex align-items-start">
                    <i class="bi bi-lightbulb-fill text-warning me-2 mt-1"></i>
                    <span class="text-secondary small fw-medium dynamic-insight" style="line-height: 1.4;">${insight}</span>
                </div>
            </div>
        </div>`;
    }
    // --- DATA LOADING ---

    async function loadTabData(category) {
        const tabPane = document.querySelector(`#${category}`);
        if (!tabPane) return;
        if (loadedTabs.has(category)) return;

        showLoading(tabPane);

        try {
            // Inyectar estilos personalizados
            injectCustomStyles();

            const url = obtenerUrlApi(category);
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Error API: ${response.status}`);
            const data = await response.json();

            tabPane.innerHTML = '';

            if (['comercial', 'inventario', 'produccion', 'calidad', 'financiera'].includes(category)) {
                await renderizarFiltroInteractivo(tabPane, category);
            }

            const contentContainer = document.createElement('div');
            contentContainer.id = `${category}-content`;
            tabPane.appendChild(contentContainer);

            const renderFunctions = {
                'produccion': renderProduccion,
                'calidad': renderCalidad,
                'comercial': window.renderComercial,
                'financiera': renderFinanciera,
                'inventario': renderInventario,
            };

            if (renderFunctions[category]) {
                if (['comercial', 'financiera'].includes(category)) {
                    // Pass utils to these modules
                    await renderFunctions[category](data, contentContainer, {
                        renderKpiCard, createSmartCardHTML, createChart, createSplitSmartCardHTML
                    });
                } else {
                    await renderFunctions[category](data, contentContainer);
                }
            }

            loadedTabs.add(category);
            // Inicializar tooltips de Bootstrap
            [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')).map(el => new bootstrap.Tooltip(el));

        } catch (error) {
            console.error(error);
            showError(tabPane, error.message);
        }
    }

    // --- RENDER LOGIC: PRODUCCIÓN ---

    function renderProduccion(data, container) {
        // Delega la renderización al archivo produccion.js
        if (typeof window.renderProduccionTab === 'function') {
            window.renderProduccionTab(data, container);
        } else {
            container.innerHTML = '<div class="alert alert-warning">Error: El módulo de gráficos de producción no se ha cargado correctamente.</div>';
            console.error("renderProduccionTab no está definido. Verifica que produccion.js esté incluido.");
        }
    }

    function renderCalidad(data, container) {
        if (typeof window.renderCalidadTab === 'function') {
            window.renderCalidadTab(data, container, {
                renderKpiCard, createSmartCardHTML, createChart, createSplitSmartCardHTML
            });
        } else {
            container.innerHTML = '<div class="alert alert-warning">Error: El módulo de gráficos de calidad no se ha cargado correctamente.</div>';
            console.error("renderCalidadTab no está definido. Verifica que calidad.js esté incluido.");
        }
    }

    function renderFinanciera(data, container) {
        // Delegar al archivo finanzas.js si está cargado
        if (typeof window.renderFinanciera === 'function') {
            window.renderFinanciera(data, container, {
                renderKpiCard, createSmartCardHTML, createChart, createSplitSmartCardHTML
            });
        } else {
            container.innerHTML = '<div class="alert alert-warning">Error: El módulo de gráficos financieros no se ha cargado correctamente.</div>';
            console.error("renderFinanciera (externo) no está definido. Verifica que finanzas.js esté incluido.");
        }
    }

    function renderInventario(data, container) {
        // Delegar al archivo inventario.js si está cargado
        if (typeof window.renderInventario === 'function') {
            window.renderInventario(data, container, {
                renderKpiCard, createChart, createSmartCardHTML
            });
        } else {
            container.innerHTML = '<div class="alert alert-warning">Error: El módulo de inventario no se ha cargado correctamente.</div>';
            console.error("renderInventario (externo) no está definido. Verifica que inventario.js esté incluido.");
        }
    }

    // --- FILTRO INTERACTIVO & ESTILOS ---

    async function renderizarFiltroInteractivo(container, category) {
        // Lógica del filtro (igual que versión anterior)
        if (!dashboardState[category]) dashboardState[category] = { period: 'semana', value: '' };
        const currentState = dashboardState[category];

        let yearOptionsHtml = '';
        if (currentState.period === 'ano') {
            try {
                const res = await fetch('/reportes/api/indicadores/anos-disponibles');
                const json = await res.json();
                if (json.success) {
                    yearOptionsHtml = json.data.map(year =>
                        `<option value="${year}" ${currentState.value == year ? 'selected' : ''}>${year}</option>`
                    ).join('');
                }
            } catch (e) { console.error(e); }
        }

        const toolbar = document.createElement('div');
        toolbar.className = 'compact-toolbar';

        const btns = {
            semana: currentState.period === 'semana' ? 'btn-primary shadow-sm fw-bold' : 'btn-outline-secondary border-0 text-muted',
            mes: currentState.period === 'mes' ? 'btn-primary shadow-sm fw-bold' : 'btn-outline-secondary border-0 text-muted',
            ano: currentState.period === 'ano' ? 'btn-primary shadow-sm fw-bold' : 'btn-outline-secondary border-0 text-muted',
        };

        let inputHtml = '';
        if (currentState.period === 'semana') inputHtml = `<input type="week" class="form-control form-control-sm bg-white border-0 shadow-sm" value="${currentState.value}" data-type="semana" style="min-width: 160px;">`;
        else if (currentState.period === 'mes') inputHtml = `<input type="month" class="form-control form-control-sm bg-white border-0 shadow-sm" value="${currentState.value}" data-type="mes" style="min-width: 160px;">`;
        else if (currentState.period === 'ano') inputHtml = `<select class="form-select form-select-sm bg-white border-0 shadow-sm" data-type="ano" style="min-width: 120px;"><option value="">Seleccionar</option>${yearOptionsHtml}</select>`;

        toolbar.innerHTML = `
            <div class="d-flex align-items-center gap-3 flex-wrap w-100 justify-content-between">
                <div class="d-flex align-items-center p-1 bg-white rounded-pill shadow-sm border">
                     <span class="px-3 py-1 text-uppercase small fw-bold text-muted me-2" style="letter-spacing: 0.5px;"><i class="bi bi-funnel-fill me-1"></i> Filtros</span>
                     <div class="vr me-2 text-secondary opacity-25"></div>
                    <button type="button" class="btn btn-sm ${btns.semana} rounded-pill px-3 transition-all period-btn" data-period="semana">Semana</button>
                    <button type="button" class="btn btn-sm ${btns.mes} rounded-pill px-3 transition-all period-btn" data-period="mes">Mes</button>
                    <button type="button" class="btn btn-sm ${btns.ano} rounded-pill px-3 transition-all period-btn" data-period="ano">Año</button>
                </div>
                
                <div class="d-flex align-items-center bg-white rounded-pill shadow-sm border px-3 py-1">
                    <span class="text-muted small fw-bold me-2 text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">Período</span>
                    ${inputHtml}
                </div>
            </div>
        `;

        toolbar.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (dashboardState[category].period !== e.target.dataset.period) {
                    dashboardState[category].period = e.target.dataset.period;
                    dashboardState[category].value = '';
                    loadedTabs.delete(category);
                    chartInstances = {};
                    loadTabData(category);
                }
            });
        });
        const inputElement = toolbar.querySelector('input, select');
        if (inputElement) {
            inputElement.addEventListener('change', (e) => {
                if (e.target.value) {
                    dashboardState[category].value = e.target.value;
                    loadedTabs.delete(category);
                    chartInstances = {};
                    loadTabData(category);
                }
            });
        }
        container.appendChild(toolbar);
    }

    function injectCustomStyles() {
        if (document.getElementById('dashboard-custom-styles')) return;
        const style = document.createElement('style');
        style.id = 'dashboard-custom-styles';
        style.innerHTML = `
            /* --- VARIABLES --- */
            :root {
                --theme-color: #0d6efd;
                --theme-rgb: 13, 110, 253;
                --theme-bg-subtle: rgba(13, 110, 253, 0.1);
            }

            /* --- ANIMATIONS --- */
            @keyframes pulse-glow {
                0% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.4); }
                70% { box-shadow: 0 0 0 6px rgba(25, 135, 84, 0); }
                100% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0); }
            }
            .pulse-badge {
                animation: pulse-glow 2s infinite;
            }

            /* --- HEADER & TABS (GLASSMORPHISM) --- */
            #dashboard-header-card {
                border-left: 4px solid var(--theme-color) !important;
            }
            
            /* Apply theme color to main icon */
            #dashboard-header-card .icon-box {
                color: var(--theme-color) !important;
                background-color: rgba(255, 255, 255, 0.9) !important;
                box-shadow: 0 4px 15px var(--theme-bg-subtle) !important;
            }

            .nav-tabs-custom {
                gap: 0.5rem;
                padding-bottom: 0.5rem;
            }
            .nav-tabs-custom .nav-link {
                border: 1px solid transparent;
                background: rgba(255, 255, 255, 0.6);
                color: #6c757d;
                font-weight: 600;
                padding: 0.6rem 1.25rem;
                border-radius: 50rem;
                transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
                font-size: 0.9rem;
            }
            .nav-tabs-custom .nav-link:hover {
                background-color: rgba(255, 255, 255, 0.9);
                transform: translateY(-1px);
                color: var(--theme-color);
            }
            
            /* Active Tab: Glass/Neon Effect */
            .nav-tabs-custom .nav-link.active {
                background: var(--theme-bg-subtle);
                color: var(--theme-color) !important;
                border: 1px solid rgba(var(--theme-rgb), 0.2);
                box-shadow: 0 4px 12px rgba(var(--theme-rgb), 0.15);
                backdrop-filter: blur(5px);
            }
            .nav-tabs-custom .nav-link.active i {
                color: var(--theme-color) !important;
            }
            
            /* --- FILTER TOOLBAR --- */
            .compact-toolbar {
                background: transparent;
                padding: 0.5rem 0;
                margin-bottom: 2rem;
                border: none;
            }
            .period-btn:hover {
                transform: translateY(-1px);
            }
            
            /* --- KPI CARDS --- */
            .kpi-card {
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                border-radius: 1rem;
            }
            .hover-lift:hover {
                transform: translateY(-6px);
                box-shadow: 0 15px 30px rgba(0,0,0,0.1), 0 5px 15px rgba(0,0,0,0.05) !important;
            }
            .transition-all { transition: all 0.3s ease; }
            .transition-transform { transition: transform 0.3s ease; }
            .kpi-card:hover .icon-box {
                transform: scale(1.1) rotate(5deg);
            }

            /* Gradient Text */
            .gradient-text-primary { background: linear-gradient(45deg, #0d6efd, #0dcaf0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .gradient-text-success { background: linear-gradient(45deg, #198754, #20c997); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .gradient-text-warning { background: linear-gradient(45deg, #ffc107, #ffcd39); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .gradient-text-danger  { background: linear-gradient(45deg, #dc3545, #f74a5d); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .gradient-text-info    { background: linear-gradient(45deg, #0dcaf0, #3dd5f3); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .gradient-text-indigo  { background: linear-gradient(45deg, #6610f2, #6f42c1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            
            /* Tooltips */
            .tooltip-inner { 
                max-width: 300px; 
                text-align: left; 
                background-color: #333;
                box-shadow: 0 8px 20px rgba(0,0,0,0.3);
                border-radius: 0.5rem;
                padding: 0.75rem;
            }
        `;
        document.head.appendChild(style);
    }

    // --- DYNAMIC THEME SWITCHER ---
    function updateTheme(category) {
        const headerCard = document.getElementById('dashboard-header-card');
        if (!headerCard) return;

        const themes = {
            'produccion': { color: '#0d6efd', rgb: '13, 110, 253' },   // Blue
            'comercial':  { color: '#0dcaf0', rgb: '13, 202, 240' },   // Cyan/Teal
            'financiera': { color: '#198754', rgb: '25, 135, 84' },    // Green
            'calidad':    { color: '#6610f2', rgb: '102, 16, 242' },   // Purple/Indigo
            'inventario': { color: '#fd7e14', rgb: '253, 126, 20' }    // Orange
        };

        const theme = themes[category] || themes['produccion'];
        
        // Set CSS Variables on the card element so they cascade to children
        headerCard.style.setProperty('--theme-color', theme.color);
        headerCard.style.setProperty('--theme-rgb', theme.rgb);
        headerCard.style.setProperty('--theme-bg-subtle', `rgba(${theme.rgb}, 0.1)`);
    }

    // --- INIT ---
    tabElements.forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const category = event.target.dataset.category;
            updateTheme(category); // Update theme on switch
            
            setTimeout(() => Object.values(chartInstances).forEach(chart => chart.resize()), 150);
            loadTabData(category);
        });
    });

    // Initial Load
    const initialActiveTab = document.querySelector('#kpiTab .nav-link.active');
    if (initialActiveTab) {
        const initialCategory = initialActiveTab.dataset.category;
        updateTheme(initialCategory);
        loadTabData(initialCategory);
    }
});