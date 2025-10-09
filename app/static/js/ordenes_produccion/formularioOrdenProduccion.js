document.addEventListener('DOMContentLoaded', function () {
    const formulario = document.getElementById("formulario");
    
    formulario.addEventListener('submit', function (event) {
        event.preventDefault();

   
        const data = {
            producto_id: parseInt(document.getElementById('producto_id').value),
            cantidad: parseFloat(document.getElementById('cantidad').value),
            fecha_planificada: document.getElementById('fecha_planificada').value,
            prioridad: document.getElementById('prioridad').value,
            observaciones: document.getElementById('observaciones').value,
            supervisor_responsable_id: document.getElementById('supervisor_responsable_id').value
        };

        let url = CREAR_URL;
        let method = 'POST';

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // La redirección mostrará el mensaje flash de éxito en el nuevo modal
                window.location.href = LISTA_URL;
            } else {
                // Mostrar error de validación en el modal
                showNotificationModal('Error de Validación', data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error en la petición:', error);
            showNotificationModal('Error de Conexión', 'No se pudo procesar la solicitud. Verifique su conexión e intente nuevamente.', 'error');
        });

        return false;
    });
});