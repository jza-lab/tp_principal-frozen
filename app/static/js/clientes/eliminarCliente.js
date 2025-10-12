function eliminarCliente(id) {
    const title = 'Confirmar Inhabilitación';
    const body = '¿Estás seguro de que quieres inhabilitar este cliente?';

    showConfirmationModal(title, body, () => {
        const url = `/administrar/clientes/${id}/eliminar`; 

        fetch(url, {
            method: 'POST',
        })
        .then(response => {
            if (!response.ok) {
                
                throw new Error(`Método no permitido o error del servidor: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showNotificationModal(
                    'Éxito', 
                    'Cliente inhabilitado correctamente.', 
                    'success', 
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo inhabilitar el cliente.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la inhabilitación:', error);
            
            showNotificationModal('Error', error.message || 'Ocurrió un error de red.', 'error');
        });
    }, 'danger');
}

function habilitarCliente(id) {
    const title = 'Confirmar Inhabilitación';
    const body = '¿Estás seguro de que quieres inhabilitar este cliente?';

    showConfirmationModal(title, body, () => {
        const url = `/administrar/clientes/${id}/habilitar`; 

        fetch(url, {
            method: 'POST',
        })
        .then(response => {
            if (!response.ok) {
                
                throw new Error(`Método no permitido o error del servidor: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showNotificationModal(
                    'Éxito', 
                    'Cliente habilitado correctamente.', 
                    'success', 
                    () => { window.location.reload(); }
                );
            } else {
                showNotificationModal('Error', data.error || 'No se pudo habilitar el cliente.', 'error');
            }
        })
        .catch(error => {
            console.error('Error en la habilitación:', error);
            
            showNotificationModal('Error', error.message || 'Ocurrió un error de red.', 'error');
        });
    }, 'danger');
}