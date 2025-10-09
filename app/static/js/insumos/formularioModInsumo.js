document.addEventListener('DOMContentLoaded', () => {
    const formulario = document.getElementById('formulario-insumo');

    formulario.addEventListener('submit', function (event) {
        event.preventDefault();

        const id_insumo = ID_INSUMO;
        const url = `/api/insumos/catalogo/actualizar/${id_insumo}`;
        const method = 'PUT';

        const data = {
            codigo_interno: document.getElementById('codigo_interno').value,
            nombre: document.getElementById('nombre').value,
            categoria: document.getElementById('categoria').value,
            unidad_medida: document.getElementById('unidad_medida').value,
            stock_min: parseFloat(document.getElementById('stock_min').value),
            stock_max: parseFloat(document.getElementById('stock_max').value),
            vida_util_dias: parseInt(document.getElementById('dias_vida_util').value),
            precio_unitario: parseInt(document.getElementById('precio_unitario').value),
            tem_recomendada: parseFloat(document.getElementById('temperatura_conservacion').value),
            descripcion: document.getElementById('descripcion').value,
            es_critico: document.getElementById('es_critico').checked,
            requiere_certificacion: document.getElementById('requiere_certificacion').checked,
            id_proveedor: parseInt(document.getElementById('proveedor').value)
        };

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(async response => {
            const result = await response.json();

            if (response.ok && result.success) {
                window.location.href = INSUMOS_LISTA_URL;
            } else {
                mostrarModalError(result.error || 'Ocurrió un error al guardar el insumo.', result.details);
            }
        })
        .catch(err => {
            mostrarModalError('Error de conexión o del servidor.');
            console.error('Error en fetch:', err);
        });
    });

    function mostrarModalError(mensaje, detalles = null) {
        let errorMsg = mensaje;
        if (detalles) {
            const detailsFormatted = Object.entries(detalles)
                .map(([field, messages]) => `<strong>${field}:</strong> ${messages.join(', ')}`)
                .join('<br>');
            errorMsg += `<br><br><div class="text-start small">${detailsFormatted}</div>`;
        }

        const notificationModal = new bootstrap.Modal(document.getElementById('notificationModal'));
        const modalTitle = document.getElementById('notificationModalTitle');
        const modalBody = document.getElementById('notificationModalBody');

        modalTitle.textContent = 'Error al actualizar insumo';
        modalBody.innerHTML = errorMsg;

        // Header en rojo
        modalTitle.parentElement.classList.remove('bg-success', 'bg-primary');
        modalTitle.parentElement.classList.add('bg-danger', 'text-white');

        notificationModal.show();
    }
});