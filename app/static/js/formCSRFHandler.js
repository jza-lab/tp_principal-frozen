document.addEventListener('DOMContentLoaded', function () {
    // Función para obtener el valor de una cookie por su nombre
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const forms = document.querySelectorAll('form[method="POST"]');
    forms.forEach(form => {
        // No interferir con los formularios que ya tienen un manejador de confirmación
        if (form.classList.contains('confirm-form') || form.classList.contains('needs-confirmation')) {
            return;
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            const formData = new FormData(form);
            const url = form.action;
            const csrfToken = getCookie('csrf_access_token');

            // Convertir FormData a URLSearchParams para enviarlo como form-urlencoded
            const urlEncodedData = new URLSearchParams(formData);

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRF-TOKEN': csrfToken
                },
                body: urlEncodedData
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    return response.json().then(data => {
                        if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        } else {
                            // Si hay mensajes flash, podrían venir en la respuesta
                            if (data.message) {
                                showNotificationModal(data.success ? 'Éxito' : 'Error', data.message, data.success ? 'success' : 'error');
                            } else {
                                window.location.reload();
                            }
                        }
                    });
                }
            })
            .catch(error => {
                console.error('Error en el envío del formulario:', error);
                showNotificationModal('Error de Red', 'No se pudo contactar con el servidor.', 'error');
            });
        });
    });
});
