document.addEventListener('DOMContentLoaded', () => {
    const formulario = document.getElementById('formulario-insumo')

    formulario.addEventListener('submit', function(event ){
        event.preventDefault();

        
        if(IS_EDIT){
            const id_insumo= ID_INSUMO
            url = `/api/insumos/catalogo/actualizar/${id_insumo}`;
        }
        else{
             url = `/api/insumos/catalogo/nuevo`;
        }
       


        const data = {
            codigo_interno: document.getElementById('codigo_interno').value,
            nombre: document.getElementById('nombre').value,
            categoria: document.getElementById('categoria').value,
            unidad_medida: document.getElementById('unidad_medida').value,
            stock_min: parseFloat(document.getElementById('stock_min').value),
            stock_max: parseFloat(document.getElementById('stock_max').value),
            vida_util_dias: parseInt(document.getElementById('dias_vida_util').value),
            tem_recomendada: parseFloat(document.getElementById('temperatura_conservacion').value),
            descripcion: document.getElementById('descripcion').value,
            es_critico: document.getElementById('es_critico').checked,
            requiere_certificacion: document.getElementById('requiere_certificacion').checked
        };

        fetch (url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if(data.success){
                alert('Operacion exitosa');
                window.location.href = INSUMOS_LISTA_URL;
            }
            else{
                alert ('Operacion fallida: '+ data.error);
            }
        })
        .catch((error) => {
            console.error('Error:',error);
            alert('Ocurrio un error');
        });
        return false; 
    });
});