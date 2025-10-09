function recargarPrecioProducto(id) {
    const title = 'Confirmar Habilitación';
    const body = '¿Quieres actualizar el precio del producto?';

        const url = `/api/productos/catalogo/actualizar-precio/${id}`;

        fetch(url, {
            method: 'GET',
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
                    'Precio del producto actualizado correctamente.',
                    'success',
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo recargar el costo el producto.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la recarga de precio:', error);
            showNotificationModal('Error', 'Ocurrió un error de red al intentar recargar el precio del producto.', 'error');
        });

}