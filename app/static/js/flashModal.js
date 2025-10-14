document.addEventListener('DOMContentLoaded', function () {
    const flashContainer = document.getElementById('flash-messages-container');
    if (flashContainer) {
        const messages = flashContainer.querySelectorAll('div[data-message]');
        if (messages.length > 0) {
            // Tomar el primer mensaje
            const firstMessage = messages[0];
            const category = firstMessage.getAttribute('data-category');
            const message = firstMessage.getAttribute('data-message');

            // Mapear la categoría de Flask a un tipo de notificación
            let modalType = 'info';
            let modalTitle = 'Notificación';

            if (category === 'success') {
                modalType = 'success';
                modalTitle = 'Éxito';
            } else if (category === 'error') {
                modalType = 'error';
                modalTitle = 'Error';
            } else if (category === 'warning') {
                modalType = 'warning';
                modalTitle = 'Advertencia';
            }
            
            // Usar la función global showNotificationModal si existe
            if (typeof showNotificationModal === 'function') {
                showNotificationModal(modalTitle, message, modalType);
            } else {
                // Fallback por si la función no está definida (aunque debería estarlo)
                alert(`${modalTitle}: ${message}`);
            }
        }
    }
});