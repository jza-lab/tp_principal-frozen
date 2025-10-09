function habilitarUsuario(id) {
    const title = 'Confirmar Habilitación';
    const body = '¿Estás seguro de que quieres habilitar este usuario?';

    showConfirmationModal(title, body, () => {
        const url = `/admin/usuarios/${id}/habilitar`;

        fetch(url, {
            method: 'POST',
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showNotificationModal(
                    'Éxito',
                    'Usuario habilitado correctamente.',
                    'success',
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo habilitar el usuario.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la habilitación:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar habilitar el usuario.', 'error');
        });
    }, 'success');
}

function eliminarUsuario(id) {
    const title = 'Confirmar Inhabilitación';
    const body = '¿Estás seguro de que quieres inhabilitar este usuario?';

    showConfirmationModal(title, body, () => {
        const url = `/admin/usuarios/${id}/eliminar`;

        fetch(url, {
            method: 'POST',
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showNotificationModal(
                    'Éxito', 
                    'Usuario inhabilitado correctamente.', 
                    'success', 
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo inhabilitar el usuario.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la inhabilitación:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar inhabilitar el usuario.', 'error');
        });
    }, 'danger');
}