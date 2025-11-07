// Sobreescribir globalmente fetch para añadir el token CSRF a las peticiones internas.
(function() {
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;

        // Solo añadir la cabecera si el token existe y la petición es interna.
        if (csrfToken && options && ['POST', 'PUT', 'DELETE'].includes(options.method?.toUpperCase()) && !url.startsWith('http')) {
            options.headers = {
                ...options.headers,
                'X-CSRFToken': csrfToken
            };
        }
        return originalFetch(url, options);
    };
})();

function showNotificationModal(title, message) {
    const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
    document.getElementById('notificationModalTitle').textContent = title;
    document.getElementById('notificationModalBody').textContent = message;
    modal.show();
}
