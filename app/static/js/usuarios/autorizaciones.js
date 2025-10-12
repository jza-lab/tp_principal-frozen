document.addEventListener('DOMContentLoaded', function() {
    const authorizationsContainer = document.getElementById('authorizations-container');

    function createAuthorizationCard(auth) {
        return `
            <div class="col-md-4 mb-4">
                <div class="card">
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

    window.updateAuthorization = function(id, estado) {
        const comentario = document.getElementById(`comentario-${id}`).value;
        fetch(`/admin/autorizaciones/${id}/estado`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ estado, comentario })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                fetchAuthorizations();
            } else {
                alert('Error al actualizar la autorización.');
            }
        });
    }

    fetchAuthorizations();
});
