// --- FUNCIÓN HELPER (FASE 3 y 4) ---
// Mueve una OP a un nuevo estado (usada por Kanban y recomendación del Kanban)
async function moverOp(opId, nuevoEstado) {
    try {
        // Usa el prefijo /planificacion para la ruta mover-op del Kanban
        const response = await fetch(`/planificacion/api/mover-op/${opId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nuevo_estado: nuevoEstado }) // Asegúrate que el estado tenga guion bajo si es necesario
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

    // --- LÓGICA DE CONSOLIDACIÓN Y RECOMENDACIÓN (KANBAN - FASE 2/3) ---
    const consolidarBtn = document.getElementById('btn-consolidar');
    if (consolidarBtn) {
        const checkboxes = document.querySelectorAll('.op-checkbox');
        // Función para habilitar/deshabilitar el botón de consolidar
        function checkSelection() {
            const seleccionados = document.querySelectorAll('.op-checkbox:checked');
            if (seleccionados.length < 2) { consolidarBtn.disabled = true; return; }
            const primerProductoId = seleccionados[0].closest('.kanban-card').dataset.productoId;
            const sonMismoProducto = Array.from(seleccionados).every(cb => cb.closest('.kanban-card').dataset.productoId === primerProductoId);
            consolidarBtn.disabled = !sonMismoProducto;
        }
        checkboxes.forEach(cb => cb.addEventListener('change', checkSelection));
        // Evento al hacer clic en consolidar
        consolidarBtn.addEventListener('click', async () => {
            const seleccionados = document.querySelectorAll('.op-checkbox:checked');
            const opIds = Array.from(seleccionados).map(cb => cb.value);
            if (!confirm(`¿Estás seguro de que quieres consolidar ${opIds.length} órdenes?`)) return;
            consolidarBtn.disabled = true; consolidarBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Consolidando...`;
            try {
                // 1. Consolidar
                const resCons = await fetch('/planificacion/api/consolidar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ op_ids: opIds }) });
                const resultCons = await resCons.json();
                if (!resultCons.success) throw new Error(resultCons.error);
                const newOP = resultCons.data;
                alert(`¡Éxito! Super OP creada: ${newOP.codigo}`);
                // 2. Recomendar
                const resRec = await fetch(`/planificacion/api/recomendar-linea/${newOP.id}`); // Ajusta prefijo si es necesario
                const resultRec = await resRec.json();
                if (resultRec.success) {
                    const rec = resultRec.data;
                    const msg = `RECOMENDACIÓN:\nLínea: ${rec.nombre_linea}\nMotivo: ${rec.motivo}\n\nPresiona "Aceptar" para usarla o "Cancelar" para la otra.`;
                    // 3. Mover (usando la función helper 'moverOp')
                    if (confirm(msg)) { await moverOp(newOP.id, `EN_LINEA_${rec.linea_sugerida}`); } // Con guion bajo
                    else { await moverOp(newOP.id, `EN_LINEA_${rec.linea_sugerida === 1 ? 2 : 1}`); } // Con guion bajo
                } else { alert('Super OP creada, pero no se pudo obtener recomendación.'); }
            } catch (error) { console.error('Error en el proceso:', error); alert('Error: ' + error.message); }
            finally { window.location.reload(); }
        });
    }

    // --- LÓGICA DE DRAG-AND-DROP (KANBAN - FASE 4) ---
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(column => {
        const cardContainer = column.querySelector('.kanban-cards');
        if (cardContainer) {
            new Sortable(cardContainer, {
                group: 'kanban',
                animation: 150,
                ghostClass: 'bg-primary-soft',
                // --- VALIDACIÓN onMove ---
                onMove: function (evt) {
                    const fromState = evt.from.closest('.kanban-column').dataset.estado;
                    const toState = evt.to.closest('.kanban-column').dataset.estado;
                    const draggedCard = evt.dragged;

                    console.log("onMove triggered:", { fromState, toState }); // Log inicial

                    // Definir transiciones permitidas
                    const allowedTransitions = {
                        'LISTA PARA PRODUCIR': ['EN_LINEA_1', 'EN_LINEA_2'],
                        'EN ESPERA': [], // No se debe mover manualmente desde aquí
                        'EN_LINEA_1': ['EN_EMPAQUETADO'],
                        'EN_LINEA_2': ['EN_EMPAQUETADO'],
                        'EN_EMPAQUETADO': ['CONTROL_DE_CALIDAD'],
                        'CONTROL_DE_CALIDAD': ['COMPLETADA'],
                        'COMPLETADA': []
                    };

                    if (!allowedTransitions[fromState] || !allowedTransitions[fromState].includes(toState)) {
                        console.warn(`Movimiento NO PERMITIDO de ${fromState} a ${toState} según allowedTransitions.`);
                        return false; // Impedir movimiento
                    }

                    // Validar línea correcta al mover desde LISTA PARA PRODUCIR
                    if (fromState === 'LISTA PARA PRODUCIR' && (toState === 'EN_LINEA_1' || toState === 'EN_LINEA_2')) {
                        const opId = draggedCard.dataset.opId;
                        const lineaAsignada = draggedCard.dataset.lineaAsignada;
                        const lineaDestino = toState === 'EN_LINEA_1' ? '1' : '2';

                        if (!lineaAsignada) {
                             console.error(`VALIDACIÓN FALLIDA (onMove): OP ${opId} no tiene data-linea-asignada.`);
                             // No mostramos alert aquí para evitar interrupciones si falla algo más
                             return false;
                        }
                        if (lineaAsignada !== lineaDestino) {
                            console.error(`VALIDACIÓN FALLIDA (onMove): Intento de mover OP ${opId} a línea incorrecta. Asignada: ${lineaAsignada}, Destino: ${lineaDestino}`);
                            // No mostramos alert aquí
                            return false; // Impedir el movimiento
                        }
                    }

                    console.log("Movimiento PERMITIDO visualmente.");
                    return true; // Permitir el movimiento si pasa las validaciones
                },
                // --- FIN VALIDACIÓN onMove ---
                onEnd: async function (evt) {
                    // Verificar si el movimiento fue revertido visualmente por onMove retornando false
                    // Si to y from son el mismo contenedor Y el índice no cambió, no pasó nada.
                    // Si to y from son el mismo PERO el índice cambió, SÍ hubo un movimiento (dentro de la misma columna).
                    // Si to es diferente de from, SÍ hubo un movimiento entre columnas.
                    // La condición importante es si SortableJS revirtió el cambio (to == from && oldIndex == newIndex)
                    // O si nosotros retornamos false en onMove (que también causa que to == from).
                    // Una forma más simple: si el elemento sigue en la lista original Y en el índice original
                    if (evt.from === evt.to && evt.oldDraggableIndex === evt.newDraggableIndex) {
                         console.log("onEnd: El elemento no cambió de posición o el movimiento fue revertido por onMove. No llamar a API.");
                         return;
                    }

                    const item = evt.item;
                    const toColumn = evt.to.closest('.kanban-column');

                    if (!toColumn || !toColumn.dataset || !toColumn.dataset.estado) {
                         console.error("onEnd: No se pudo determinar el estado de destino. Abortando API call y revirtiendo.");
                         // Intentar revertir visualmente
                         evt.from.insertBefore(item, evt.from.children[evt.oldDraggableIndex]);
                         return;
                    }

                    const opId = item.dataset.opId;
                    const nuevoEstado = toColumn.dataset.estado;

                    console.log(`onEnd: Llamando a API para mover OP #${opId} a estado: ${nuevoEstado}`);
                    const success = await moverOp(opId, nuevoEstado);

                    if (!success) {
                        console.error("onEnd: API falló. Revertiendo movimiento visual.");
                        // Intentar revertir visualmente
                        evt.from.insertBefore(item, evt.from.children[evt.oldDraggableIndex]);
                    } else {
                        console.log(`onEnd: API exitosa para mover OP #${opId}.`);
                        // Opcional: Recargar o actualizar contadores si es necesario
                        // window.location.reload(); // Descomentar si la recarga es la forma más fácil
                    }
                } // Fin onEnd
            }); // Fin new Sortable
        } // Fin if cardContainer
    }); // Fin columns.forEach

    // =======================================================
    // --- JAVASCRIPT DE LA NUEVA BANDEJA DE PLANIFICACIÓN ---
    // =======================================================
    const tablaPlanificacion = document.querySelector('.planificador-tabla tbody');
    if (tablaPlanificacion) {
        tablaPlanificacion.addEventListener('click', async function(e) {
            const botonCalcular = e.target.closest('.btn-calcular');
            const botonPreAsignar = e.target.closest('.btn-pre-asignar');
            const botonConfirmar = e.target.closest('.btn-confirmar-inicio');

            // --- Lógica para Calcular Sugerencia ---
            if (botonCalcular) {
                const fila = botonCalcular.closest('tr'); const opId = fila.dataset.opId;
                const celdaSugerencia = fila.querySelector('.resultado-sugerencia');
                const celdaAcciones = fila.querySelector('.celda-acciones');

                botonCalcular.disabled = true;
                celdaSugerencia.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Calculando...';
                celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-info';
                celdaSugerencia.style.display = 'block';

                try {
                    const response = await fetch(`/ordenes/${opId}/sugerir-inicio`); // URL corregida
                    const result = await response.json();

                    if (result.success) {
                        const data = result.data;
                        let htmlSugerencia = `<strong>Inicio Sugerido: <span class="fs-6">${data.fecha_inicio_sugerida}</span></strong> `;
                        htmlSugerencia += `(Línea Sug.: <b>${data.linea_sugerida}</b>)<hr class="my-1">`;
                        htmlSugerencia += `Plazo Total: <b>${data.plazo_total_dias} días</b><br>`;
                        htmlSugerencia += `<ul><li>Producción: ${data.t_produccion_dias} días</li>`;
                        if (data.t_aprovisionamiento_dias > 0) {
                            htmlSugerencia += `<li>Compras: ${data.t_aprovisionamiento_dias} días (Stock Faltante)</li>`;
                            celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-warning';
                        } else {
                            htmlSugerencia += `<li>Compras: 0 días (Stock OK)</li>`;
                            celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-success';
                        }
                        htmlSugerencia += `</ul>`;
                        if (data.recomendacion_eficiencia) {
                            htmlSugerencia += `<p class="mb-0 mt-2 text-danger"><small><i class="bi bi-exclamation-triangle-fill"></i> ${data.recomendacion_eficiencia}</small></p>`;
                            if (celdaSugerencia.className.includes('alert-success')) { celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-warning'; }
                        }
                        celdaSugerencia.innerHTML = htmlSugerencia;
                        botonCalcular.style.display = 'none';

                        // Añadir controles (Selects + Botón Pre-Asignar)
                        let lineaSelectHTML = `<select class="form-select form-select-sm mb-1 select-linea" title="Seleccionar Línea">`;
                        lineaSelectHTML += `<option value="1" ${data.linea_sugerida === 1 ? 'selected' : ''}>Línea 1</option>`;
                        lineaSelectHTML += `<option value="2" ${data.linea_sugerida === 2 ? 'selected' : ''}>Línea 2</option>`;
                        lineaSelectHTML += `</select>`;
                        let supervisorSelectHTML = `<select class="form-select form-select-sm mb-1 select-supervisor" title="Asignar Supervisor">`;
                        supervisorSelectHTML += `<option value="">Supervisor (Opcional)</option>`;
                        listaSupervisores.forEach(sup => { supervisorSelectHTML += `<option value="${sup.id}">${sup.nombre} ${sup.apellido || ''}</option>`; });
                        supervisorSelectHTML += `</select>`;
                        let operarioSelectHTML = `<select class="form-select form-select-sm mb-1 select-operario" title="Asignar Operario">`;
                        operarioSelectHTML += `<option value="">Operario (Opcional)</option>`;
                        listaOperarios.forEach(op => { operarioSelectHTML += `<option value="${op.id}">${op.nombre} ${op.apellido || ''}</option>`; });
                        operarioSelectHTML += `</select>`;
                        const botonPreAsignarHTML = `<button class="btn btn-info btn-sm btn-pre-asignar w-100" data-op-id="${opId}">Guardar Asignación</button>`;
                        celdaAcciones.innerHTML = lineaSelectHTML + supervisorSelectHTML + operarioSelectHTML + botonPreAsignarHTML;

                    } else { /* Manejo error cálculo */ celdaSugerencia.innerHTML = `Error: ${result.error}`; celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-danger'; botonCalcular.disabled = false; }
                } catch (error) { /* Manejo error conexión */ console.error("Error al calcular sugerencia:", error); celdaSugerencia.innerHTML = 'Error de conexión.'; celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-danger'; botonCalcular.disabled = false; }
            }

            // --- Guardar Asignación ---
            else if (botonPreAsignar) {
                const fila = botonPreAsignar.closest('tr'); const opId = botonPreAsignar.dataset.opId;
                const lineaSelect = fila.querySelector('.select-linea'); const supervisorSelect = fila.querySelector('.select-supervisor');
                const operarioSelect = fila.querySelector('.select-operario'); const celdaAcciones = fila.querySelector('.celda-acciones');
                const celdaSugerencia = fila.querySelector('.resultado-sugerencia');
                const fechaSugeridaElement = celdaSugerencia.querySelector('strong > span');
                const fechaSugeridaISO = fechaSugeridaElement ? fechaSugeridaElement.textContent : new Date().toISOString().split('T')[0];

                botonPreAsignar.disabled = true; botonPreAsignar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Guardando...`;

                try {
                    const response = await fetch(`/ordenes/${opId}/pre-asignar`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            linea_asignada: parseInt(lineaSelect.value),
                            supervisor_responsable_id: supervisorSelect.value ? parseInt(supervisorSelect.value) : null,
                            operario_asignado_id: operarioSelect.value ? parseInt(operarioSelect.value) : null
                        })
                    });
                    const result = await response.json();
                    if (result.success) {
                        let fechaInputHTML = `<label for="fecha-inicio-${opId}" class="form-label form-label-sm visually-hidden">Inicio Confirmado:</label>`;
                        fechaInputHTML += `<input type="date" id="fecha-inicio-${opId}" class="form-control form-control-sm mb-1 input-fecha-inicio" value="${fechaSugeridaISO}" title="Confirmar Fecha de Inicio">`;
                        const botonConfirmarHTML = `<button class="btn btn-success btn-sm btn-confirmar-inicio w-100" data-op-id="${opId}">Confirmar Inicio y Aprobar</button>`;
                        celdaAcciones.innerHTML = fechaInputHTML + botonConfirmarHTML;
                    } else { alert(`Error al guardar asignación: ${result.error}`); botonPreAsignar.disabled = false; botonPreAsignar.textContent = 'Guardar Asignación'; }
                } catch (error) { console.error("Error al pre-asignar:", error); alert('Error de conexión.'); botonPreAsignar.disabled = false; botonPreAsignar.textContent = 'Guardar Asignación'; }
            }

            // --- Confirmar Inicio y Aprobar ---
            else if (botonConfirmar) {
                 const fila = botonConfirmar.closest('tr'); const opId = botonConfirmar.dataset.opId;
                 const fechaInput = fila.querySelector('.input-fecha-inicio'); const celdaAcciones = fila.querySelector('.celda-acciones');
                 const fechaSeleccionada = fechaInput.value;
                 if (!fechaSeleccionada) { alert("Seleccione la fecha de inicio."); return; }
                 botonConfirmar.disabled = true; botonConfirmar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Confirmando...`;
                 try {
                     const response = await fetch(`/ordenes/${opId}/confirmar-inicio`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                         body: JSON.stringify({ fecha_inicio_planificada: fechaSeleccionada })
                     });
                     const result = await response.json();
                     if (result.success) { alert(result.message || "OP confirmada."); fila.remove(); window.location.reload(); }
                     else { alert(`Error al confirmar: ${result.error}`); botonConfirmar.disabled = false; botonConfirmar.textContent = 'Confirmar y Aprobar'; }
                 } catch (error) { console.error("Error al confirmar inicio:", error); alert('Error de conexión.'); botonConfirmar.disabled = false; botonConfirmar.textContent = 'Confirmar y Aprobar'; }
            }
        }); // Fin addEventListener
    } // Fin if tablaPlanificacion

}); // Fin del DOMContentLoaded