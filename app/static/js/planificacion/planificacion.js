// --- FUNCIÓN HELPER (FASE 3 y 4) ---
// Mueve una OP a un nuevo estado (usada por Kanban y recomendación del Kanban)
async function moverOp(opId, nuevoEstado) {
    try {
        const response = await fetch(`/planificacion/api/mover-op/${opId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nuevo_estado: nuevoEstado })
        });
        const result = await response.json();
        if (!result.success) {
            console.error(`Error al mover la OP ${opId}: ${result.error}`);
            alert(`Hubo un error al mover la OP: ${result.error}`);
        }
        return result.success;
    } catch (error) {
        console.error(`Error de red al mover la OP ${opId}:`, error);
        alert('Error de conexión. No se pudo guardar el cambio.');
        return false;
    }
}

document.addEventListener('DOMContentLoaded', function () {

    // --- LÓGICA DE CONSOLIDACIÓN (KANBAN) ---
    const consolidarBtn = document.getElementById('btn-consolidar');
    if (consolidarBtn) {
        const checkboxes = document.querySelectorAll('.op-checkbox');
        function checkSelection() {
            const seleccionados = document.querySelectorAll('.op-checkbox:checked');
            if (seleccionados.length < 2) { consolidarBtn.disabled = true; return; }
            const primerProductoId = seleccionados[0].closest('.kanban-card').dataset.productoId;
            const sonMismoProducto = Array.from(seleccionados).every(cb => cb.closest('.kanban-card').dataset.productoId === primerProductoId);
            consolidarBtn.disabled = !sonMismoProducto;
        }
        checkboxes.forEach(cb => cb.addEventListener('change', checkSelection));
        consolidarBtn.addEventListener('click', async () => {
            const seleccionados = document.querySelectorAll('.op-checkbox:checked');
            const opIds = Array.from(seleccionados).map(cb => cb.value);
            if (!confirm(`¿Estás seguro de que quieres consolidar ${opIds.length} órdenes?`)) return;
            consolidarBtn.disabled = true; consolidarBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Consolidando...`;
            try {
                // Llama a la API de consolidación simple (del Kanban)
                const resCons = await fetch('/planificacion/api/consolidar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ op_ids: opIds }) });
                const resultCons = await resCons.json();
                if (!resultCons.success) throw new Error(resultCons.error);
                const newOP = resultCons.data;
                alert(`¡Éxito! Super OP creada: ${newOP.codigo}`);
                
                // Llama a la API de recomendación (del Kanban)
                const resRec = await fetch(`/planificacion/api/recomendar-linea/${newOP.id}`);
                const resultRec = await resRec.json();
                if (resultRec.success) {
                    const rec = resultRec.data;
                    const msg = `RECOMENDACIÓN:\nLínea: ${rec.nombre_linea}\nMotivo: ${rec.motivo}\n\nPresiona "Aceptar" para usarla o "Cancelar" para la otra.`;
                    if (confirm(msg)) { await moverOp(newOP.id, `EN_LINEA_${rec.linea_sugerida}`); }
                    else { await moverOp(newOP.id, `EN_LINEA_${rec.linea_sugerida === 1 ? 2 : 1}`); }
                } else { alert('Super OP creada, pero no se pudo obtener recomendación.'); }
            } catch (error) { console.error('Error en el proceso:', error); alert('Error: ' + error.message); }
            finally { window.location.reload(); }
        });
    }

    // --- LÓGICA DE DRAG-AND-DROP (KANBAN) ---
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(column => {
        const cardContainer = column.querySelector('.kanban-cards');
        if (cardContainer) {
            new Sortable(cardContainer, {
                group: 'kanban', animation: 150, ghostClass: 'bg-primary-soft',
                onMove: function (evt) {
                    const fromState = evt.from.closest('.kanban-column').dataset.estado;
                    const toState = evt.to.closest('.kanban-column').dataset.estado;
                    const draggedCard = evt.dragged;
                    const allowedTransitions = { 'LISTA PARA PRODUCIR': ['EN_LINEA_1', 'EN_LINEA_2'], 'EN ESPERA': [], 'EN_LINEA_1': ['EN_EMPAQUETADO'], 'EN_LINEA_2': ['EN_EMPAQUETADO'], 'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD'], 'CONTROL_DE_CALIDAD': ['COMPLETADA'], 'COMPLETADA': [] };
                    if (!allowedTransitions[fromState] || !allowedTransitions[fromState].includes(toState)) { return false; }
                    if (fromState === 'LISTA PARA PRODUCIR' && (toState === 'EN_LINEA_1' || toState === 'EN_LINEA_2')) {
                        const opId = draggedCard.dataset.opId; const lineaAsignada = draggedCard.dataset.lineaAsignada;
                        const lineaDestino = toState === 'EN_LINEA_1' ? '1' : '2';
                        if (!lineaAsignada) { console.error(`VALIDACIÓN FALLIDA (onMove): OP ${opId} no tiene data-linea-asignada.`); return false; }
                        if (lineaAsignada !== lineaDestino) { console.error(`VALIDACIÓN FALLIDA (onMove): Intento de mover OP ${opId} a línea incorrecta. Asignada: ${lineaAsignada}, Destino: ${lineaDestino}`); return false; }
                    }
                    return true;
                },
                onEnd: async function (evt) {
                    if (evt.from === evt.to && evt.oldDraggableIndex === evt.newDraggableIndex) { return; }
                    const item = evt.item; const toColumn = evt.to.closest('.kanban-column');
                    if (!toColumn || !toColumn.dataset || !toColumn.dataset.estado) { evt.from.insertBefore(item, evt.from.children[evt.oldDraggableIndex]); return; }
                    const opId = item.dataset.opId; const nuevoEstado = toColumn.dataset.estado;
                    const success = await moverOp(opId, nuevoEstado);
                    if (!success) { evt.from.insertBefore(item, evt.from.children[evt.oldDraggableIndex]); }
                }
            });
        }
    });

    // =======================================================
    // --- JAVASCRIPT DE LA BANDEJA DE PLANIFICACIÓN (MODAL) ---
    // =======================================================
    
    document.addEventListener('click', async function(e) {
        
        // --- NUEVA LÓGICA: BOTÓN CONSOLIDAR Y APROBAR ---
        const botonConsolidarAprobar = e.target.closest('.btn-consolidar-y-aprobar');
        
        if (botonConsolidarAprobar) {
            const modal = botonConsolidarAprobar.closest('.modal');
            if (!modal) {
                console.error("No se encontró la modal contenedora."); return;
            }

            // 1. Obtener la lista de IDs de OP a consolidar (del atributo data-)
            let opIds = [];
            try {
                opIds = JSON.parse(modal.dataset.opIds || '[]');
            } catch (err) {
                console.error("Error al parsear op-ids:", err);
            }
            if (opIds.length === 0) {
                 alert("Error: No se encontraron IDs de Órdenes de Producción para consolidar."); return;
            }

            // 2. Obtener los datos del formulario de asignación
            const lineaSelect = modal.querySelector('.modal-select-linea');
            const supervisorSelect = modal.querySelector('.modal-select-supervisor');
            const operarioSelect = modal.querySelector('.modal-select-operario');
            const fechaInput = modal.querySelector('.modal-input-fecha-inicio');

            if (!fechaInput.value) { alert("Por favor, seleccione una Fecha de Inicio."); return; }
            if (!lineaSelect.value) { alert("Por favor, seleccione una Línea."); return; }

            const asignaciones = {
                fecha_inicio: fechaInput.value,
                linea_asignada: parseInt(lineaSelect.value),
                supervisor_id: supervisorSelect.value ? parseInt(supervisorSelect.value) : null,
                operario_id: operarioSelect.value ? parseInt(operarioSelect.value) : null
            };

            // 3. Enviar a la NUEVA API
            botonConsolidarAprobar.disabled = true;
            botonConsolidarAprobar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Procesando Lote...`;

            try {
                const response = await fetch('/planificacion/api/consolidar-y-aprobar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        op_ids: opIds,
                        asignaciones: asignaciones
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    alert(result.message || "Lote consolidado y aprobado con éxito.");
                    window.location.reload(); // Recargar la página para ver los cambios
                } else {
                    alert(`Error al planificar el lote: ${result.error}`);
                    botonConsolidarAprobar.disabled = false;
                    botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
                }

            } catch (error) {
                console.error("Error de red al consolidar y aprobar:", error);
                alert('Error de conexión. No se pudo planificar el lote.');
                botonConsolidarAprobar.disabled = false;
                botonConsolidarAprobar.innerHTML = '<i class="bi bi-check-lg"></i> Consolidar y Aprobar Lote';
            }
        } // Fin if (botonConsolidarAprobar)


        // --- Lógica para Calcular Sugerencia (Individual, en modal) ---
        // (Esta lógica se mantiene por si quieres calcular la referencia)
        const botonCalcular = e.target.closest('.btn-calcular');
        if (botonCalcular) {
            const fila = botonCalcular.closest('tr'); 
            if (!fila) { console.error("No se encontró TR para Calcular"); return; }
            const opId = fila.dataset.opId;
            if (!opId) { console.error("TR para Calcular no tiene data-op-id"); return; }

            const celdaSugerencia = fila.querySelector('.resultado-sugerencia');
            
            botonCalcular.disabled = true;
            botonCalcular.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            celdaSugerencia.innerHTML = 'Calculando...';
            celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-info';
            celdaSugerencia.style.display = 'block';

            try {
                // Llama a la API de sugerencia individual
                const response = await fetch(`/ordenes/${opId}/sugerir-inicio`);
                const result = await response.json();

                if (result.success) {
                    const data = result.data;
                    let htmlSugerencia = `<small>In. Sug.: ${data.fecha_inicio_sugerida} (L: ${data.linea_sugerida}) | Plazo: ${data.plazo_total_dias}d (P:${data.t_produccion_dias}d + C:${data.t_aprovisionamiento_dias}d)</small>`;
                    
                    if (data.t_aprovisionamiento_dias > 0) {
                        celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-warning';
                    } else {
                        celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-success';
                    }
                    celdaSugerencia.innerHTML = htmlSugerencia;
                    botonCalcular.style.display = 'none'; // Ocultar botón
                } else { 
                    celdaSugerencia.innerHTML = `Error: ${result.error}`; 
                    celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-danger'; 
                    botonCalcular.disabled = false; 
                    botonCalcular.innerHTML = '<i class="bi bi-calculator-fill"></i> Calcular Ref.';
                }
            } catch (error) { 
                console.error("Error al calcular sugerencia:", error); 
                celdaSugerencia.innerHTML = 'Error de conexión.'; 
                celdaSugerencia.className = 'resultado-sugerencia mt-1 alert alert-danger'; 
                botonCalcular.disabled = false; 
                botonCalcular.innerHTML = '<i class="bi bi-calculator-fill"></i> Calcular Ref.';
            }
        } // Fin if (botonCalcular)
        
    }); // Fin addEventListener 'click' en 'document'

}); // Fin del DOMContentLoaded