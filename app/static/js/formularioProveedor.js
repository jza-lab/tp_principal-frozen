document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formulario-proveedor');

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();

        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return;
        }
        const formData = new FormData(form);
        const proveedorData = {
            nombre: formData.get('nombre'),
            cuit: formData.get('cuit'),
            telefono: formData.get('telefono'),
            email: formData.get('email'),
            direccion: formData.get('direccion'),
            condicion_iva: formData.get('condicion_iva')
        };
        const url = isEditBoolean ? `/administrar/proveedores/${ID_proveedor}/editar` : '/administrar/proveedores/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const respuesta = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(proveedorData)
                });
                const resultado = await respuesta.json();

                if (respuesta.ok && resultado.success) {
                showNotificationModal(resultado.message || 'Operación exitosa', 'success');
                setTimeout(() => { window.location.href = proveedorS_LISTA_URL; }, 1500);
            } else {
                let errorMessage = 'Ocurrió un error.';
                if (resultado && resultado.error) {
                    errorMessage = typeof resultado.error === 'object' ? Object.values(resultado.error).flat().join('\n') : resultado.error;
                }
                showNotificationModal(errorMessage, 'error');
            }
        } catch (error) {

            console.error('Error:', error);
            showNotificationModal('No se pudo conectar con el servidor.', 'error');

        }});
});
