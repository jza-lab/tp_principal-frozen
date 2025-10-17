document.addEventListener('DOMContentLoaded', function() {
    const panels = {
        'users-panel': {
            initializer: EmpleadosPanel.init,
            initialized: false
        },
        'activity-panel': {
            initializer: ActividadPanel.init,
            initialized: false
        },
        'authorizations-panel': {
            initializer: AutorizacionesPanel.init,
            initialized: false
        }
    };

    function initializePanel(panelId) {
        if (panels[panelId] && !panels[panelId].initialized) {
            panels[panelId].initializer();
            panels[panelId].initialized = true;
        }
    }

    // Inicializar el panel activo por defecto al cargar la página
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (activeTabPane) {
        initializePanel(activeTabPane.id);
    }

    // Añadir listeners para inicializar los paneles al cambiar de pestaña
    const tabButtons = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabButtons.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(event) {
            const panelId = event.target.getAttribute('data-bs-target').substring(1);
            initializePanel(panelId);
        });
    });
});