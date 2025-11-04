document.addEventListener('DOMContentLoaded', function () {
    // Listener para todos los botones "Iniciar Trabajo"
    document.querySelectorAll('.btn-iniciar-op').forEach(button => {
        button.addEventListener('click', function () {
            const opId = this.dataset.opId;
            if (opId) {
                // Redirigir a la nueva vista de foco
                window.location.href = `/tabla-produccion/foco/${opId}`;
            } else {
                console.error('No se pudo encontrar el ID de la orden en el botón.');
                // Opcional: mostrar un mensaje de error al usuario
                alert('Error: No se pudo identificar la orden de producción. Contacte a soporte.');
            }
        });
    });
});
