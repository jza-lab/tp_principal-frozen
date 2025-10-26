document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formulario-cliente');
    if (!form) return;

    async function enviarDatos() {
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            showNotificationModal('Formulario Incompleto', 'Por favor, complete todos los campos requeridos.');
            return;
        }

        const contrasena = document.getElementById('contrasena').value;
        const confirm_contrasena = document.getElementById('confirm_contrasena').value;

        if (contrasena !== confirm_contrasena) {
            showNotificationModal('Error de Contraseña', 'Las contraseñas no coinciden.');
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
            razon_social: formData.get('razon_social') || '',
            contrasena: contrasena,
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

        console.log(clienteData)

        const url = '/cliente/register';
        const method = 'POST';

        try {
            const respuesta = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(clienteData)
            });

            const resultado = await respuesta.json();

            if (respuesta.ok && resultado.success) {
                showNotificationModal('¡Registro Exitoso!', 'Su cuenta ha sido creada. Será redirigido para iniciar sesión.');
                setTimeout(() => {
                    window.location.href = '/cliente/login';
                }, 2500);
            } else {
                let errorMessage = 'Ocurrió un error en el registro.';
                if (resultado && resultado.error) {
                    errorMessage = typeof resultado.error === 'object' ? Object.values(resultado.error).flat().join('<br>') : resultado.error;
                }
                showNotificationModal('Error de Registro', errorMessage);
            }
        } catch (error) {
            console.error('Error:', error);
            showNotificationModal('Error de Conexión', 'No se pudo conectar con el servidor. Inténtelo más tarde.');
        }
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        event.stopPropagation();
        enviarDatos();
    });
});
