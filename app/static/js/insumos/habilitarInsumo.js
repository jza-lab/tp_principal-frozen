function habilitarInsumo(id) {
    const title = 'Confirmar Habilitación';
    const body = '¿Estás seguro de que quieres habilitar este insumo?';

    showConfirmationModal(title, body, () => {
        const url = `/api/insumos/catalogo/habilitar/${id}`;

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
                    'Insumo habilitado correctamente.',
                    'success',
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo habilitar el insumo.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la habilitación:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar habilitar el insumo.', 'error');
        });
    }, 'success');
}