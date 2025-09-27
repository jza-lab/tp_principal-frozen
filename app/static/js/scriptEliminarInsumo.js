function eliminarInsumo(id){
    const confirmacion = confirm("¿Quieres eliminar este insumo?")

    if(!confirmacion){
        return;
    }

    const url = `/api/insumos/catalogo/eliminar/${id}`;

    fetch(url, {
        method: 'DELETE', 
    })
    .then(response => {
        // Asegúrate de que la respuesta tenga un estado aceptable (200 o 204)
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Insumo desactivado correctamente.');
            window.location.reload(); 
        } else {
            alert('Error al desactivar: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error en la eliminación lógica:', error);
        alert('Ocurrió un error al intentar desactivar el insumo.');
    });
}