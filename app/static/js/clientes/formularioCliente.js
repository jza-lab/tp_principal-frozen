document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formulario-cliente');

    const calleInput = document.getElementById('calle');
    const alturaInput = document.getElementById('altura');
    const provinciaSelect = document.getElementById('provincia');
    const localidadInput = document.getElementById('localidad');


    async function enviarDatos() {
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return;
        }

        const formData = new FormData(form);
        const cuit = `${formData.get('cuit_parte1')}-${formData.get('cuit_parte2')}-${formData.get('cuit_parte3')}`;
        const clienteData = {
            nombre: formData.get('nombre'),
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

        const url = isEditBoolean ? `/administrar/clientes/${ID_cliente}/editar` : '/administrar/clientes/nuevo';
        const method = isEditBoolean ? 'PUT' : 'POST';

        try {
            const respuesta = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(clienteData)
            });
            const resultado = await respuesta.json();

            if (respuesta.ok && resultado.success) {
                const mensaje = isEditBoolean ? 'Los datos del cliente se actualizaron correctamente.' : 'Se creó un nuevo cliente exitosamente';
                showNotificationModal(resultado.message || 'Operación exitosa', mensaje);
                setTimeout(() => { window.location.href = clienteS_LISTA_URL; }, 1500);
            } else {
                let errorMessage = 'Ocurrió un error.';
                if (resultado && resultado.error) {
                    errorMessage = typeof resultado.error === 'object' ? Object.values(resultado.error).flat().join('\n') : resultado.error;
                }
                const mensaje = isEditBoolean ? 'Hubo un fallo al actualizar los datos del cliente.' : 'Hubo un fallo al crear al cliente.';
                showNotificationModal(errorMessage, mensaje);
            }
        } catch (error) {
            console.error('Error:', error);
            showNotificationModal('No se pudo conectar con el servidor.', 'error');
        }
    };

    async function verifyAddress() {
        try {
            const response = await fetch('/api/validar/direccion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calle: calleInput.value,
                    altura: alturaInput.value,
                    localidad: localidadInput.value,
                    provincia: provinciaSelect.value
                })
            });

            const verificationResult = await response.json();

            if (response.ok && verificationResult.success) {
                await enviarDatos();
            } else {
                let errorMessage = 'Dirección no válida o error de verificación.';
                if (verificationResult && verificationResult.error) {
                    errorMessage = verificationResult.error;
                }
                showNotificationModal(errorMessage, 'Error al verificar la dirección');
                form.classList.add('was-validated');
            }
        } catch (error) {
            console.error('Error de red al verificar la direccion:', error);
            showNotificationModal('No se pudo conectar con el servidor de verificación.', 'error');
        }
    }

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        event.stopPropagation();

        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return;
        }

        await verifyAddress();
    });

});