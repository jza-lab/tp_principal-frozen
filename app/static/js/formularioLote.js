document.addEventListener('DOMContentLoaded', function () {
    const formLote = document.getElementById('form-lote');

    if (formLote) {
        formLote.addEventListener('submit', function(event) {
            event.preventDefault();

            const submitButton = document.getElementById('submit-lote');
            const isEdit = formLote.dataset.isEdit === 'true';
            const formAction = isEdit ? formLote.dataset.editUrl : formLote.dataset.createUrl;
            const redirectUrl = formLote.dataset.redirectUrl;

            const originalButtonText = submitButton.innerHTML;
            submitButton.disabled = true;
            submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${isEdit ? 'Guardando...' : 'Registrando...'}`;

            const formData = new FormData(formLote);
            let data = {};

            if (isEdit) {
                // En modo edición, solo enviamos los campos que pueden cambiar
                data = {
                    cantidad_actual: parseFloat(formData.get('cantidad_actual')),
                    f_vencimiento: formData.get('fecha_vencimiento'),
                    precio_unitario: formData.get('precio_unitario') ? parseFloat(formData.get('precio_unitario')) : null,
                    observaciones: formData.get('observaciones')
                };
            } else {
                // En modo creación, enviamos todos los campos necesarios
                data = {
                    id_insumo: formData.get('id_insumo'),
                    id_proveedor: parseInt(formData.get('proveedor_id')),
                    cantidad_inicial: parseFloat(formData.get('cantidad_inicial')),
                    f_ingreso: formData.get('fecha_ingreso'),
                    f_vencimiento: formData.get('fecha_vencimiento'),
                    documento_ingreso: formData.get('documento_ingreso'),
                    precio_unitario: formData.get('precio_unitario') ? parseFloat(formData.get('precio_unitario')) : null,
                    observaciones: formData.get('observaciones')
                };
            }

            fetch(formAction, {
                method: isEdit ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            })
            .then(response => {
                if (!response.ok) {
                    // Si la respuesta no es OK, intentamos parsear el JSON para obtener el error
                    return response.json().then(err => Promise.reject(err));
                }
                return response.json();
            })
            .then(result => {
                if (result.success) {
                    window.location.href = redirectUrl;
                } else {
                    // Este bloque podría no alcanzarse si el error se maneja en el .catch
                    let errorMsg = result.error || 'Ocurrió un error desconocido.';
                    if (result.details) {
                        errorMsg += ': ' + JSON.stringify(result.details);
                    }
                    alert(`Falla al ${isEdit ? 'actualizar' : 'crear'} lote: ${errorMsg}`);
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalButtonText;
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
                let errorMsg = error.error || 'Error de conexión o del servidor.';
                if (error.details) {
                    // Formatear los detalles para una mejor legibilidad
                    const details = Object.entries(error.details).map(([field, messages]) => 
                        `<strong>${field}:</strong> ${messages.join(', ')}`
                    ).join('<br>');
                    errorMsg += `<br><br><div class="text-start small">${details}</div>`;
                }

                // Usar el modal de notificación en lugar de alert()
                const notificationModal = new bootstrap.Modal(document.getElementById('notificationModal'));
                const modalTitle = document.getElementById('notificationModalTitle');
                const modalBody = document.getElementById('notificationModalBody');

                modalTitle.textContent = `Error al ${isEdit ? 'Actualizar' : 'Crear'} Lote`;
                modalBody.innerHTML = errorMsg;
                
                // Cambiar el color del header a rojo para errores
                modalTitle.parentElement.classList.remove('bg-success', 'bg-primary');
                modalTitle.parentElement.classList.add('bg-danger', 'text-white');


                notificationModal.show();

                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
            });
        });
    }
});