document.addEventListener('DOMContentLoaded', function() {
    const pendingContainer = document.getElementById('pending-authorizations-container');
    const historyContainer = document.getElementById('history-authorizations-container');

    function createPendingCard(auth) {
        return `
            <div class="col-md-4 mb-4">
                <div class="card auth-card pending" data-auth-id="${auth.id}">
                    <div class="card-body">
                        <h5 class="card-title">${auth.usuario.nombre} ${auth.usuario.apellido}</h5>
                        <h6 class="card-subtitle mb-2 text-muted">Legajo: ${auth.usuario.legajo}</h6>
                        <p class="card-text mb-2">
                            <strong>Fecha:</strong> ${auth.fecha_autorizada}<br>
                            <strong>Turno:</strong> ${auth.turno.nombre} (${auth.turno.hora_inicio.slice(0, 5)} - ${auth.turno.hora_fin.slice(0, 5)})<br>
                            <strong>Tipo:</strong> ${auth.tipo.replace('_', ' ')}<br>
                            <strong>Motivo:</strong> ${auth.motivo || 'No especificado'}
                        </p>
                        <div class="mb-3">
                            <label for="comentario-${auth.id}" class="form-label small">Comentario del Supervisor</label>
                            <textarea class="form-control form-control-sm" id="comentario-${auth.id}" rows="2" placeholder="Opcional..."></textarea>
                        </div>
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-sm btn-success" onclick="updateAuthorization(${auth.id}, 'APROBADO')">Aprobar</button>
                            <button class="btn btn-sm btn-danger" onclick="updateAuthorization(${auth.id}, 'RECHAZADO')">Rechazar</button>
                        </div>
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
                            <strong>Tipo:</strong> ${auth.tipo.replace('_', ' ')}
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
        // Render pendientes
        if (data.pendientes && data.pendientes.length > 0) {
            pendingContainer.innerHTML = data.pendientes.map(createPendingCard).join('');
        } else {
            pendingContainer.innerHTML = '<div class="col-12"><div class="empty-state"><i class="bi bi-clock-history"></i><h4>No hay autorizaciones pendientes</h4><p>Todas las solicitudes han sido gestionadas.</p></div></div>';
        }

        // Render historial
        if (data.historial && data.historial.length > 0) {
            historyContainer.innerHTML = data.historial.map(createHistoryCard).join('');
        } else {
            historyContainer.innerHTML = '<div class="col-12"><div class="empty-state"><i class="bi bi-collection"></i><h4>No hay historial disponible</h4><p>Aún no se han completado autorizaciones.</p></div></div>';
        }
    }

    function fetchAuthorizations() {
        fetch('/admin/autorizaciones')
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    renderAuthorizations(result.data);
                } else {
                    pendingContainer.innerHTML = '<p class="text-danger">Error al cargar autorizaciones.</p>';
                    historyContainer.innerHTML = '<p class="text-danger">Error al cargar el historial.</p>';
                }
            })
            .catch(() => {
                pendingContainer.innerHTML = '<p class="text-danger">Error de red.</p>';
                historyContainer.innerHTML = '<p class="text-danger">Error de red.</p>';
            });
    }

    function showFlashMessage(message, category) {
        const container = document.getElementById('flash-container');
        if (!container) return;

        const alert = document.createElement('div');
        alert.className = `alert alert-${category} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        container.appendChild(alert);

        setTimeout(() => {
            alert.classList.remove('show');
            alert.addEventListener('transitionend', () => alert.remove());
        }, 5000);
    }

    window.updateAuthorization = function(id, estado) {
        const comentario = document.getElementById(`comentario-${id}`).value;
        const actionText = estado === 'APROBADO' ? 'aprobar' : 'rechazar';
        const confirmation = confirm(`¿Estás seguro de que quieres ${actionText} esta autorización?`);

        if (confirmation) {
            fetch(`/admin/autorizaciones/${id}/estado`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ estado, comentario })
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    showFlashMessage(result.message || 'Autorización actualizada.', 'success');
                    fetchAuthorizations(); // Recargar ambas listas
                } else {
                    showFlashMessage(result.error || 'Error al actualizar la autorización.', 'danger');
                }
            })
            .catch(() => {
                showFlashMessage('Error de red al actualizar la autorización.', 'danger');
            });
        }
    }

    // Carga inicial
    const authTab = document.getElementById('authorizations-tab');
    if (authTab) {
        authTab.addEventListener('shown.bs.tab', fetchAuthorizations);
    }
    // Si la pestaña de autorizaciones ya está activa al cargar la página
    if (document.querySelector('#authorizations-panel.active')) {
       fetchAuthorizations();
    }
});