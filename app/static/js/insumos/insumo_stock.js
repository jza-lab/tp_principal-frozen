document.addEventListener('DOMContentLoaded', function() {
    const updateStockButtons = document.querySelectorAll('.update-stock-btn');
    
    if (updateStockButtons.length === 0) {
        return;
    }

    updateStockButtons.forEach(button => {
        button.addEventListener('click', function() {
            const insumoId = this.dataset.id;
            const icon = this.querySelector('i');
            const stockValueSpan = document.getElementById(`stock-value-${insumoId}`);

            if (!icon || !stockValueSpan) {
                console.error(`Elements for insumo ID ${insumoId} not found.`);
                return;
            }

            this.disabled = true;
            icon.classList.remove('bi-arrow-clockwise');
            icon.classList.add('spinner-border', 'spinner-border-sm');

            fetch(`/api/insumos/catalogo/actualizar-stock/${insumoId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    stockValueSpan.textContent = data.data.stock_actual;
                    if (typeof showNotificationModal === 'function') {
                        showNotificationModal('Éxito', data.message, 'success');
                    }
                } else {
                    if (typeof showNotificationModal === 'function') {
                        showNotificationModal('Error', data.error || 'Error al actualizar el stock.', 'error');
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('Error de Red', 'Ocurrió un error de red al intentar actualizar el stock.', 'error');
                }
            })
            .finally(() => {
                this.disabled = false;
                icon.classList.remove('spinner-border', 'spinner-border-sm');
                icon.classList.add('bi-arrow-clockwise');
            });
        });
    });
});