document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formulario-proveedor');

    const calleInput = document.getElementById('calle');
    const alturaInput = document.getElementById('altura');
    const provinciaSelect = document.getElementById('provincia');
    const localidadInput = document.getElementById('localidad');

async function enviarDatos(csrfToken) {

        const formData = new FormData(form);
        const cuit = `${formData.get('cuit_parte1')}-${formData.get('cuit_parte2')}-${formData.get('cuit_parte3')}`;

        const proveedorData = {
            nombre: formData.get('nombre'),
            codigo: formData.get('codigo'),
            cuit: cuit,
            email: formData.get('email'),
            telefono: formData.get('telefono'),
            condicion_iva: formData.get('condicion_iva'),
            direccion: {
                calle: formData.get('calle'),
                altura: formData.get('altura'),
                localidad: formData.get('localidad'),
                provincia: formData.get('provincia'),
                codigo_postal: formData.get('codigo_postal'),
                piso: formData.get('piso') || null,
                depto: formData.get('depto') || null
            }
        };

        const url = isEditBoolean ? `/administrar/proveedores/${ID_proveedor}/editar` : '/administrar/proveedores/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const respuesta = await fetch(url, {
                method: method,
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
                body: JSON.stringify(proveedorData)
            });
            const resultado = await respuesta.json();

            if (respuesta.ok && resultado.success) {
                const mensaje = isEditBoolean ? 'Los datos del proveedor se actualizaron correctamente.' : 'Se creó un nuevo proveedor exitosamente';
                showNotificationModal(resultado.message || 'Operación exitosa', mensaje);
                setTimeout(() => { window.location.href = proveedorS_LISTA_URL; }, 1500);
            } else {
                let errorMessage = 'Ocurrió un error.';
                if (resultado && resultado.error) {
                    errorMessage = typeof resultado.error === 'object' ? Object.values(resultado.error).flat().join('\n') : resultado.error;
                }
                const mensaje = isEditBoolean ? 'Hubo un fallo al actualizar los datos del proveedor.' : 'Hubo un fallo al crear al proveedor.';
                showNotificationModal(errorMessage, mensaje);
            }
        } catch (error) {
            console.error('Error:', error);
            showNotificationModal('No se pudo conectar con el servidor.', '');
        }
    };

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();

        form.classList.add('was-validated');
        if (!form.checkValidity()) {
            return;
        }
        
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        await enviarDatos(csrfToken);
    });

});