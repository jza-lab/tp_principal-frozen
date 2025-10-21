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
                group: 'kanban', animation: 150, ghostClass: 'bg-primary-soft',
                onEnd: async function (evt) {
                    const item = evt.item; const toColumn = evt.to.closest('.kanban-column');
                    const opId = item.dataset.opId; const nuevoEstado = toColumn.dataset.estado; // Ej: EN_LINEA_1
                    const success = await moverOp(opId, nuevoEstado); // Llama a la función helper
                    if (!success) { evt.from.appendChild(item); } // Revertir si falla
                }
            });
        }
    });

    // =======================================================
    // --- FIN FIX NAVEGACIÓN ---
    // =======================================================

    // =======================================================
    // --- JAVASCRIPT DE LA NUEVA BANDEJA DE PLANIFICACIÓN ---
    // =======================================================
    const tablaPlanificacion = document.querySelector('.planificador-tabla tbody');
    if (tablaPlanificacion) {
        tablaPlanificacion.addEventListener('click', async function(e) {
            const botonCalcular = e.target.closest('.btn-calcular');
            const botonPreAsignar = e.target.closest('.btn-pre-asignar'); // Nombre actualizado
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

                        // --- AÑADIR CONTROLES DE ASIGNACIÓN (Selects + Botón Pre-Asignar) ---
                        let lineaSelectHTML = `<select class="form-select form-select-sm mb-1 select-linea" title="Seleccionar Línea">`;
                        lineaSelectHTML += `<option value="1" ${data.linea_sugerida === 1 ? 'selected' : ''}>Línea 1</option>`;
                        lineaSelectHTML += `<option value="2" ${data.linea_sugerida === 2 ? 'selected' : ''}>Línea 2</option>`;
                        lineaSelectHTML += `</select>`;
                        let supervisorSelectHTML = `<select class="form-select form-select-sm mb-1 select-supervisor" title="Asignar Supervisor">`;
                        supervisorSelectHTML += `<option value="">Supervisor (Opcional)</option>`;
                        // Accedemos a la variable global inyectada desde el HTML
                        listaSupervisores.forEach(sup => { supervisorSelectHTML += `<option value="${sup.id}">${sup.nombre} ${sup.apellido || ''}</option>`; });
                        supervisorSelectHTML += `</select>`;
                        let operarioSelectHTML = `<select class="form-select form-select-sm mb-1 select-operario" title="Asignar Operario">`;
                        operarioSelectHTML += `<option value="">Operario (Opcional)</option>`;
                        // Accedemos a la variable global inyectada desde el HTML
                        listaOperarios.forEach(op => { operarioSelectHTML += `<option value="${op.id}">${op.nombre} ${op.apellido || ''}</option>`; });
                        operarioSelectHTML += `</select>`;
                        // Ahora el botón es btn-pre-asignar
                        const botonPreAsignarHTML = `<button class="btn btn-info btn-sm btn-pre-asignar w-100" data-op-id="${opId}">Guardar Asignación</button>`;
                        celdaAcciones.innerHTML = lineaSelectHTML + supervisorSelectHTML + operarioSelectHTML + botonPreAsignarHTML;

                    } else {
                        celdaSugerencia.innerHTML = `Error: ${result.error}`; celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-danger'; botonCalcular.disabled = false;
                    }
                } catch (error) {
                     celdaSugerencia.innerHTML = 'Error de conexión.'; celdaSugerencia.className = 'resultado-sugerencia sugerencia-calculada alert alert-danger'; botonCalcular.disabled = false;
                }
            }

            // --- Lógica para el botón "Guardar Asignación" ---
            else if (botonPreAsignar) {
                const fila = botonPreAsignar.closest('tr'); const opId = botonPreAsignar.dataset.opId;
                const lineaSelect = fila.querySelector('.select-linea');
                const supervisorSelect = fila.querySelector('.select-supervisor');
                const operarioSelect = fila.querySelector('.select-operario');
                const celdaAcciones = fila.querySelector('.celda-acciones');
                const celdaSugerencia = fila.querySelector('.resultado-sugerencia');
                
                const fechaSugeridaElement = celdaSugerencia.querySelector('strong > span');
                const fechaSugeridaISO = fechaSugeridaElement ? fechaSugeridaElement.textContent : new Date().toISOString().split('T')[0];

                botonPreAsignar.disabled = true; botonPreAsignar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Guardando...`;

                try {
                    const response = await fetch(`/ordenes/${opId}/pre-asignar`, { // URL corregida
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            linea_asignada: parseInt(lineaSelect.value),
                            supervisor_responsable_id: supervisorSelect.value ? parseInt(supervisorSelect.value) : null,
                            operario_asignado_id: operarioSelect.value ? parseInt(operarioSelect.value) : null
                        })
                    });
                    const result = await response.json();
                    if (result.success) {
                        // Reemplazar controles con input de fecha y botón Confirmar
                        let fechaInputHTML = `<label for="fecha-inicio-${opId}" class="form-label form-label-sm visually-hidden">Inicio Confirmado:</label>`;
                        fechaInputHTML += `<input type="date" id="fecha-inicio-${opId}" class="form-control form-control-sm mb-1 input-fecha-inicio" value="${fechaSugeridaISO}" title="Confirmar Fecha de Inicio">`;
                        const botonConfirmarHTML = `<button class="btn btn-success btn-sm btn-confirmar-inicio w-100" data-op-id="${opId}">Confirmar Inicio y Aprobar</button>`;
                        celdaAcciones.innerHTML = fechaInputHTML + botonConfirmarHTML;
                    } else {
                        alert(`Error al guardar asignación: ${result.error}`); botonPreAsignar.disabled = false; botonPreAsignar.textContent = 'Guardar Asignación';
                    }
                } catch (error) {
                    alert('Error de conexión al guardar asignación.'); botonPreAsignar.disabled = false; botonPreAsignar.textContent = 'Guardar Asignación';
                }
            }

            // --- Lógica para el botón "Confirmar Inicio y Aprobar" ---
            else if (botonConfirmar) {
                 const fila = botonConfirmar.closest('tr'); const opId = botonConfirmar.dataset.opId;
                 const fechaInput = fila.querySelector('.input-fecha-inicio');
                 const celdaAcciones = fila.querySelector('.celda-acciones');

                 const fechaSeleccionada = fechaInput.value;
                 if (!fechaSeleccionada) { alert("Seleccione la fecha de inicio."); return; }

                 botonConfirmar.disabled = true; botonConfirmar.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Confirmando...`;

                 try {
                     const response = await fetch(`/ordenes/${opId}/confirmar-inicio`, { // URL corregida
                         method: 'POST', headers: { 'Content-Type': 'application/json' },
                         body: JSON.stringify({ fecha_inicio_planificada: fechaSeleccionada })
                     });
                     const result = await response.json();
                     if (result.success) {
                         alert(result.message || "OP confirmada y aprobada.");
                         fila.remove(); window.location.reload();
                     } else {
                         alert(`Error al confirmar: ${result.error}`); botonConfirmar.disabled = false; botonConfirmar.textContent = 'Confirmar y Aprobar';
                     }
                 } catch (error) {
                      alert('Error de conexión al confirmar.'); botonConfirmar.disabled = false; botonConfirmar.textContent = 'Confirmar y Aprobar';
                 }
            }
        });
    }
});

</script>