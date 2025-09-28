document.addEventListener('DOMContentLoaded', function () {
    const formulario = document.getElementById("formulario");
    
    formulario.addEventListener('submit', function (event) {
        event.preventDefault();

   
        const data = {
            producto_id: parseInt(document.getElementById('producto_id').value),
            receta_id:1,
            cantidad_planificada: parseFloat(document.getElementById('cantidad').value),
            fecha_planificada: document.getElementById('fecha_planificada').value,
            usuario_id: parseInt(document.getElementById('operario_asignado').value),
            prioridad: document.getElementById('prioridad').value,
            observaciones: document.getElementById('observaciones').value, // Asumiendo que existe este campo
            estado: 'PENDIENTE',
        };

        let url = CREAR_URL;
        let method = 'POST';

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Orden ${ES_EDICION ? 'actualizada' : 'creada'} exitosamente.`);
                window.location.href = LISTA_URL;
            } else {
                // Manejo de errores de validación de Flask/Marshmallow
                alert('Operacion fallida: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error en la petición:', error);
            alert('Ocurrió un error al procesar la orden: ' + error.message);
        });

        return false;
    });
});