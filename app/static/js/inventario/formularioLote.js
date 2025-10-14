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
                    // El mensaje flash de éxito se mostrará en el modal en la página de redirección
                    window.location.href = redirectUrl;
                } else {
                    // Este caso es para errores de validación que no lanzan una excepción HTTP
                    const errorMsg = result.error || 'Ocurrió un error desconocido.';
                    showNotificationModal(`Error al ${isEdit ? 'Actualizar' : 'Crear'} Lote`, errorMsg, 'error');
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalButtonText;
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
                let errorMsg = error.error || 'Error de conexión o del servidor.';
                // Si hay detalles de validación, los formateamos como HTML
                if (error.details) {
                    const details = Object.entries(error.details).map(([field, messages]) => 
                        `<strong>${field.replace(/_/g, ' ')}:</strong> ${messages.join(', ')}`
                    ).join('<br>');
                    errorMsg = `Se encontraron los siguientes errores:<br><br><div class="text-start small">${details}</div>`;
                }
                
                // Usamos la función genérica mejorada
                showNotificationModal(`Error al ${isEdit ? 'Actualizar' : 'Crear'} Lote`, errorMsg, 'error');

                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
            });
        });
    }
});