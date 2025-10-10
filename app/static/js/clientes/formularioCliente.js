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
        const proveedorData = {
            nombre: formData.get('nombre'),
            cuit: cuit,
            email: formData.get('email'),
            telefono:formData.get('telefono'),
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
                body: JSON.stringify(proveedorData)
            });
            const resultado = await respuesta.json();

            if (respuesta.ok && resultado.success) {
                showNotificationModal(resultado.message || 'Operación exitosa', 'success');
                setTimeout(() => { window.location.href = clienteS_LISTA_URL; }, 1500);
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
        }
    };
    
    async function verifyAddress() {
        try {
            const response = await fetch('/admin/usuarios/verificar_direccion', {
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
                showNotificationModal(errorMessage, 'error');
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