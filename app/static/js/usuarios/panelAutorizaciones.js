const AutorizacionesPanel = (function() {
    // --- ELEMENTOS DEL DOM (privados) ---
    let pendingContainer;
    let historyContainer;
    let confirmationModal;

    // --- FUNCIONES (privadas) ---
    function createPendingCard(auth) {
        const actionButtons = CAN_MANAGE_AUTHORIZATIONS ? `
            <div class="mb-3">
                <label for="comentario-${auth.id}" class="form-label small">Comentario del Supervisor</label>
                <textarea class="form-control form-control-sm" id="comentario-${auth.id}" rows="2" placeholder="Opcional..."></textarea>
            </div>
            <div class="d-flex justify-content-between">
                <button class="btn btn-sm btn-success btn-approve" data-id="${auth.id}" data-estado="APROBADO">Aprobar</button>
                <button class="btn btn-sm btn-danger btn-reject" data-id="${auth.id}" data-estado="RECHAZADO">Rechazar</button>
            </div>
        ` : '<p class="text-muted small">No tiene permisos para gestionar esta autorización.</p>';

        return `
            <div class="col-md-4 mb-4">
                <div class="card auth-card pending" data-auth-id="${auth.id}">
                    <div class="card-body">
                        <h5 class="card-title">${auth.usuario.nombre} ${auth.usuario.apellido}</h5>
                        <h6 class="card-subtitle mb-2 text-muted">Legajo: ${auth.usuario.legajo}</h6>
                        <p class="card-text mb-2">
                            <strong>Fecha:</strong> ${auth.fecha_autorizada}<br>
                            <strong>Turno:</strong> ${auth.turno.nombre} (${auth.turno.hora_inicio.slice(0, 5)} - ${auth.turno.hora_fin.slice(0, 5)})<br>
                            <strong>Tipo:</strong> ${auth.tipo.replace(/_/g, ' ')}<br>
                            <strong>Motivo:</strong> ${auth.motivo || 'No especificado'}
                        </p>
                        ${actionButtons}
                    </div>
                </div>
            </div>
        `;
    }

    function createHistoryCard(auth) {
        const statusClass = auth.estado === 'APROBADO' ? 'success' : 'danger';
        const statusIcon = auth.estado === 'APROBADO' ? 'check-circle-fill' : 'x-circle-fill';

        return `
            <div class="col-md-4 mb-4">
                <div class="card auth-card history border-${statusClass}">
                    <div class="card-header bg-light-soft">
                        <span class="badge bg-${statusClass}-soft text-${statusClass}">
                            <i class="bi bi-${statusIcon} me-1"></i>
                            ${auth.estado}
                        </span>
                    </div>
                    <div class="card-body">
                        <h5 class="card-title">${auth.usuario.nombre} ${auth.usuario.apellido}</h5>
                        <h6 class="card-subtitle mb-2 text-muted">Legajo: ${auth.usuario.legajo}</h6>
                        <p class="card-text small">
                            <strong>Fecha:</strong> ${auth.fecha_autorizada}<br>
                            <strong>Turno:</strong> ${auth.turno.nombre} (${auth.turno.hora_inicio.slice(0, 5)} - ${auth.turno.hora_fin.slice(0, 5)})<br>
                            <strong>Tipo:</strong> ${auth.tipo.replace(/_/g, ' ')}
                        </p>
                        ${auth.comentario_supervisor ? `
                        <div class="supervisor-comment">
                            <strong class="small">Comentario:</strong>
                            <p class="mb-0 fst-italic">"${auth.comentario_supervisor}"</p>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    function renderAuthorizations(data) {
        pendingContainer.innerHTML = (data.pendientes && data.pendientes.length > 0)
            ? data.pendientes.map(createPendingCard).join('')
            : '<div class="col-12"><div class="empty-state"><i class="bi bi-clock-history"></i><h4>No hay autorizaciones pendientes</h4><p>Todas las solicitudes han sido gestionadas.</p></div></div>';

        historyContainer.innerHTML = (data.historial && data.historial.length > 0)
            ? data.historial.map(createHistoryCard).join('')
            : '<div class="col-12"><div class="empty-state"><i class="bi bi-collection"></i><h4>No hay historial disponible</h4><p>Aún no se han completado autorizaciones.</p></div></div>';
    }

    function fetchAuthorizations() {
        fetch('/admin/autorizaciones')
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    renderAuthorizations(result.data);
                } else {
                    showFlashMessage('Error al cargar autorizaciones.', 'danger');
                }
            })
            .catch(() => showFlashMessage('Error de red al cargar autorizaciones.', 'danger'));
    }

    function showFlashMessage(message, category) {
        const container = document.getElementById('flash-container');
        if (!container) return;
        const alert = document.createElement('div');
        alert.className = `alert alert-${category} alert-dismissible fade show m-3`;
        alert.role = 'alert';
        alert.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
        container.appendChild(alert);
        setTimeout(() => alert.remove(), 5000);
    }

    function handleUpdateAuthorization(id, estado) {
        const comentario = document.getElementById(`comentario-${id}`).value;
        
        fetch(`/admin/autorizaciones/${id}/estado`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify({ estado, comentario })
        })
        .then(response => response.json())
        .then(result => {
            showFlashMessage(result.message || result.error || 'Acción completada.', result.success ? 'success' : 'danger');
            if (result.success) {
                fetchAuthorizations();
            }
        })
        .catch(() => showFlashMessage('Error de red al actualizar la autorización.', 'danger'))
        .finally(() => confirmationModal.hide());
    }

    function bindEvents() {
        pendingContainer.addEventListener('click', function(e) {
            const button = e.target.closest('.btn-approve, .btn-reject');
            if (!button) return;

            const id = button.dataset.id;
            const estado = button.dataset.estado;
            const actionText = estado === 'APROBADO' ? 'aprobar' : 'rechazar';
            
            document.getElementById('confirmationModalLabel').textContent = `Confirmar ${actionText.charAt(0).toUpperCase() + actionText.slice(1)}`;
            document.getElementById('confirmationModalText').textContent = `¿Estás seguro de que quieres ${actionText} esta autorización?`;
            
            const confirmBtn = document.getElementById('confirmActionBtn');
            confirmBtn.className = `btn ${estado === 'APROBADO' ? 'btn-success' : 'btn-danger'}`;
            confirmBtn.textContent = estado === 'APROBADO' ? 'Aprobar' : 'Rechazar';

            const newConfirmBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
            
            newConfirmBtn.addEventListener('click', () => handleUpdateAuthorization(id, estado), { once: true });
            
            confirmationModal.show();
        });
    }

    // --- MÉTODO PÚBLICO ---
    function init() {
        pendingContainer = document.getElementById('pending-authorizations-container');
        historyContainer = document.getElementById('history-authorizations-container');
        
        if (!pendingContainer) return;

        confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));

        fetchAuthorizations();
        bindEvents();
        console.log("Panel de Autorizaciones inicializado.");
    }

    return {
        init: init
    };
})();