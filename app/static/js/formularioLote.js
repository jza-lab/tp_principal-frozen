document.addEventListener('DOMContentLoaded', function () {
    const formRegistrarLote = document.getElementById('form-registrar-lote');

    if (formRegistrarLote) {
        formRegistrarLote.addEventListener('submit', function(event) {
            event.preventDefault();

            const submitButton = document.getElementById('crear_lote');
            const formAction = formRegistrarLote.dataset.action;
            const redirectUrl = formRegistrarLote.dataset.redirectUrl;

            submitButton.disabled = true;
            submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Registrando...`;

            const formData = new FormData(formRegistrarLote);
            const data = {
                id_insumo: formData.get('id_insumo'),
                id_proveedor: parseInt(formData.get('proveedor_id')),
                cantidad_inicial: parseFloat(formData.get('cantidad')),
                f_ingreso: formData.get('fecha_ingreso'),
                f_vencimiento: formData.get('fecha_vencimiento'),
                documento_ingreso: formData.get('numero_factura'),
                precio_unitario: formData.get('precio_unitario') ? parseFloat(formData.get('precio_unitario')) : null,
                observaciones: `Temperatura de almacenamiento: ${formData.get('temperatura_almacenamiento')} °C`
            };
            fetch(formAction, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    alert("Lote generado con éxito")
                    window.location.href = redirectUrl;
                } else {
                    let errorMsg = result.error || 'Ocurrió un error desconocido.';
                    alert("Falla al generar lote:", errorMsg)
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
            })
        });
    }
});