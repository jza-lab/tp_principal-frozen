document.addEventListener('DOMContentLoaded', function() {
    const authorizationsContainer = document.getElementById('authorizations-container');

    function createAuthorizationCard(auth) {
        return `
            <div class="col-md-4 mb-4">
                <div class="card" data-auth-id="${auth.id}">
                    <div class="card-body">
                        <h5 class="card-title">${auth.usuario.nombre} ${auth.usuario.apellido}</h5>
                        <p class="card-text">
                            <strong>Legajo:</strong> ${auth.usuario.legajo}<br>
                            <strong>Fecha:</strong> ${auth.fecha_autorizada}<br>
                            <strong>Turno:</strong> ${auth.turno.nombre} (${auth.turno.hora_inicio.slice(0, 5)} - ${auth.turno.hora_fin.slice(0, 5)})<br>
                            <strong>Motivo:</strong> ${auth.motivo || 'No especificado'}
                        </p>
                        <div class="mb-3">
                            <label for="comentario-${auth.id}" class="form-label">Comentario</label>
                            <textarea class="form-control" id="comentario-${auth.id}" rows="2"></textarea>
                        </div>
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-success" onclick="updateAuthorization(${auth.id}, 'APROBADO')">Aprobar</button>
                            <button class="btn btn-danger" onclick="updateAuthorization(${auth.id}, 'RECHAZADO')">Rechazar</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function fetchAuthorizations() {
        fetch('/admin/autorizaciones')
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    authorizationsContainer.innerHTML = '';
                    result.data.forEach(auth => {
                        authorizationsContainer.innerHTML += createAuthorizationCard(auth);
                    });
                } else {
                    authorizationsContainer.innerHTML = '<p>No hay autorizaciones pendientes.</p>';
                }
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
        const card = document.querySelector(`.card[data-auth-id="${id}"]`);
        const comentario = document.getElementById(`comentario-${id}`).value;

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
                
                // Actualizar la UI de la tarjeta
                const actions = card.querySelector('.d-flex');
                
                // Crear el badge de estado
                const statusBadge = document.createElement('span');
                statusBadge.className = `badge bg-${estado === 'APROBADO' ? 'success' : 'danger'}`;
                statusBadge.textContent = estado;

                // Reemplazar los botones con el badge
                actions.innerHTML = '';
                actions.appendChild(statusBadge);

                // Cambiar el estilo de la tarjeta
                card.classList.add(estado === 'APROBADO' ? 'border-success' : 'border-danger');

            } else {
                showFlashMessage(result.error || 'Error al actualizar la autorización.', 'danger');
            }
        })
        .catch(() => {
            showFlashMessage('Error de red al actualizar la autorización.', 'danger');
        });
    }

    fetchAuthorizations();
});
