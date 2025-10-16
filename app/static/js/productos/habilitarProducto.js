function habilitarProducto(id) {
    const title = 'Confirmar Habilitación';
    const body = '¿Estás seguro de que quieres habilitar este producto?';

    showConfirmationModal(title, body, () => {
        const url = `/catalogo/habilitar/${id}`;

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
                    'Producto habilitado correctamente.',
                    'success',
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo habilitar el producto.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la habilitación:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar habilitar el producto.', 'error');
        });
    }, 'success');
}