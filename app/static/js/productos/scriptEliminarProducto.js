function eliminarProducto(id) {
    const title = 'Confirmar Inhabilitación';
    const body = '¿Estás seguro de que quieres inhabilitar este producto?';

    showConfirmationModal(title, body, () => {
        const url = `/catalogo/eliminar/${id}`;

        fetch(url, {
            method: 'DELETE',
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
                    'Producto inhabilitado correctamente.', 
                    'success', 
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo inhabilitar el producto.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la inhabilitación:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar inhabilitar el producto.', 'error');
        });
    }, 'danger');
}