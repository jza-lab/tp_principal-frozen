/**
 * Muestra un modal de confirmación genérico con dos botones (Confirmar/Cancelar).
 * @param {string} title - El título del modal.
 * @param {string} body - El mensaje en el cuerpo del modal.
 * @param {function} confirmCallback - La función que se ejecutará si el usuario hace clic en "Confirmar".
 * @param {string} [buttonType='primary'] - El estilo del botón de confirmación ('primary', 'success', 'danger').
 */
function showConfirmationModal(title, body, confirmCallback, buttonType = 'primary') {
    const modalElement = document.getElementById('confirmationModal');
    if (!modalElement) {
        console.error('Modal element #confirmationModal not found in the DOM.');
        return;
    }

    const modalTitle = modalElement.querySelector('#modalTitle');
    const modalBody = modalElement.querySelector('#modalBody');
    const modalConfirmButton = modalElement.querySelector('#modalConfirmButton');
    const modalCancelButton = modalElement.querySelector('#modalCancelButton');

    // Asignar contenido y configurar botones
    modalTitle.textContent = title;
    modalBody.textContent = body;
    modalConfirmButton.textContent = 'Confirmar';
    modalConfirmButton.className = `btn btn-${buttonType}`; // Asignar clase de estilo
    modalCancelButton.style.display = ''; // Asegurarse de que el botón Cancelar esté visible

    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    // Clonar y reemplazar el botón para limpiar listeners de eventos anteriores
    const newConfirmButton = modalConfirmButton.cloneNode(true);
    modalConfirmButton.parentNode.replaceChild(newConfirmButton, modalConfirmButton);
    
    // Asignar el nuevo callback
    newConfirmButton.addEventListener('click', () => {
        confirmCallback();
        modal.hide();
    });

    modal.show();
}

/**
 * Muestra un modal de notificación con un solo botón (OK).
 * @param {string} title - El título del modal.
 * @param {string} body - El mensaje en el cuerpo del modal.
 * @param {string} [type='info'] - El tipo de notificación ('success', 'error', 'info') para colorear el botón.
 * @param {function} [closeCallback] - (Opcional) La función que se ejecutará después de que el modal se cierre.
 */
function showNotificationModal(title, body, type = 'info', closeCallback) {
    const modalElement = document.getElementById('notificationModal');
    if (!modalElement) {
        console.error('Modal element #notificationModal not found in the DOM.');
        return;
    }

    const modalTitle = modalElement.querySelector('#notificationModalTitle');
    const modalBody = modalElement.querySelector('#notificationModalBody');
    const modalOkButton = modalElement.querySelector('#notificationModalOkButton');

    // Asignar contenido y configurar botones
    modalTitle.textContent = title;
    modalBody.textContent = body;

    // Cambiar color del botón según el tipo de notificación
    let buttonClass = 'btn btn-primary';
    if (type === 'success') {
        buttonClass = 'btn btn-success';
    } else if (type === 'error') {
        buttonClass = 'btn btn-danger';
    }
    modalOkButton.className = buttonClass;

    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    // Si hay un callback, lo ejecutamos DESPUÉS de que el modal se oculte.
    // Usamos { once: true } para que el listener se elimine automáticamente después de ejecutarse una vez.
    if (closeCallback && typeof closeCallback === 'function') {
        modalElement.addEventListener('hidden.bs.modal', closeCallback, { once: true });
    }

    modal.show();
}