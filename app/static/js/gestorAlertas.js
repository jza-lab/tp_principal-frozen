document.addEventListener('DOMContentLoaded', function() {
    const modalElement = document.getElementById('modalCrearAlerta');
    if (!modalElement) return;

    const modal = new bootstrap.Modal(modalElement);
    const origenEntidadNombre = document.getElementById('origen-entidad-nombre');
    const previsualizacionContenido = document.getElementById('previsualizacion-contenido');
    const form = document.getElementById('formCrearAlerta');
    const btnConfirmar = document.getElementById('btnConfirmarCrearAlerta');

    document.body.addEventListener('click', function(event) {
        const target = event.target.closest('.btn-crear-alerta');
        if (target) {
            const tipoEntidad = target.dataset.tipoEntidad;
            const idEntidad = target.dataset.idEntidad;
            const nombreEntidad = target.dataset.nombreEntidad;

            origenEntidadNombre.textContent = `${nombreEntidad} (ID: ${idEntidad})`;
            form.elements['tipo_entidad'].value = tipoEntidad;
            form.elements['id_entidad'].value = idEntidad;

            previsualizacionContenido.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Cargando...</span></div></div>';
            modal.show();

            fetch(`/riesgos/api/previsualizar?tipo_entidad=${tipoEntidad}&id_entidad=${idEntidad}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        renderPrevisualizacion(data.data.afectados_detalle);
                    } else {
                        previsualizacionContenido.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                    }
                })
                .catch(error => {
                    previsualizacionContenido.innerHTML = `<div class="alert alert-danger">Error de red: ${error}</div>`;
                });
        }
    });

    btnConfirmar.addEventListener('click', async function() {
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        btnConfirmar.disabled = true;
        btnConfirmar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...';

        let urlEvidencia = null;
        const evidenciaFile = form.elements['evidencia'].files[0];

        if (evidenciaFile) {
            const formData = new FormData();
            formData.append('evidencia', evidenciaFile);
            
            try {
                const response = await fetch('/riesgos/api/subir_evidencia', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': document.querySelector('#csrf_token').value },
                    body: formData
                });
                const data = await response.json();
                if (!data.success) {
                    throw new Error(data.error || 'Error al subir el archivo.');
                }
                urlEvidencia = data.url;
            } catch (error) {
                alert(`Error al subir la evidencia: ${error.message}`);
                btnConfirmar.disabled = false;
                btnConfirmar.innerHTML = 'Crear Alerta';
                return;
            }
        }

        const alertaData = {
            tipo_entidad: form.elements['tipo_entidad'].value,
            id_entidad: form.elements['id_entidad'].value,
            motivo: form.elements['motivo'].value,
            comentarios: form.elements['comentarios'].value,
            url_evidencia: urlEvidencia
        };

        try {
            const response = await fetch('/riesgos/api/crear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('#csrf_token').value
                },
                body: JSON.stringify(alertaData)
            });
            const data = await response.json();
            if (data.success) {
                window.location.href = `/admin/riesgos/${data.data.codigo}/detalle`;
            } else {
                throw new Error(data.error || 'Error al crear la alerta.');
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
            btnConfirmar.disabled = false;
            btnConfirmar.innerHTML = 'Crear Alerta';
        }
    });

    function renderPrevisualizacion(detalles) {
        let html = '';
        if (detalles.pedidos && detalles.pedidos.length > 0) {
            html += '<h5>Pedidos Afectados</h5><ul class="list-group mb-3">';
            detalles.pedidos.forEach(p => {
                html += `<li class="list-group-item">${p.id} - ${p.nombre_cliente}</li>`;
            });
            html += '</ul>';
        }
        if (detalles.lotes_producto && detalles.lotes_producto.length > 0) {
            html += '<h5>Lotes de Producto Afectados</h5><ul class="list-group mb-3">';
            detalles.lotes_producto.forEach(l => {
                html += `<li class="list-group-item">${l.numero_lote}</li>`;
            });
            html += '</ul>';
        }
        if (detalles.ordenes_produccion && detalles.ordenes_produccion.length > 0) {
            html += '<h5>Órdenes de Producción Afectadas</h5><ul class="list-group mb-3">';
            detalles.ordenes_produccion.forEach(op => {
                html += `<li class="list-group-item">${op.codigo}</li>`;
            });
            html += '</ul>';
        }
        if (html === '') {
            html = '<div class="alert alert-info">No se encontraron otras entidades afectadas.</div>';
        }
        previsualizacionContenido.innerHTML = html;
    }
});
