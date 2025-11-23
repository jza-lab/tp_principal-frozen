/**
 * Sistema de Ayuda Interactiva para el Tablero de Planificación.
 * Permite activar un modo "Ayuda" que muestra botones informativos sobre elementos clave.
 */

const helpData = [
    {
        selector: '#btn-forzar-auto-planificacion',
        title: 'Forzar Auto-Planificación',
        content: `
            <p><strong>¿Qué hace?</strong><br>
            Ejecuta el algoritmo de inteligencia artificial que revisa todas las órdenes en estado <em>Pendiente</em> y trata de asignarles automáticamente una línea, fecha y turno.</p>
            <p><strong>¿Cuándo usarlo?</strong><br>
            Úselo cuando tenga nuevas órdenes pendientes y quiera que el sistema sugiera el mejor plan posible sin hacerlo manualmente.</p>
        `
    },
    {
        selector: '#btn-forzar-verificacion-capacidad',
        title: 'Forzar Verificación',
        content: `
            <p><strong>¿Qué hace?</strong><br>
            Analiza todo el plan de la semana actual buscando conflictos (ej: sobrecarga de línea, falta de materiales). Si encuentra problemas, genera "Notificaciones" o "Issues".</p>
            <p><strong>¿Cuándo usarlo?</strong><br>
            Ideal después de agregar un bloqueo de mantenimiento o cambiar la configuración de una línea, para ver inmediatamente si afecta a las órdenes ya programadas.</p>
        `
    },
    {
        selector: 'a[href*="configuracion_lineas"]',
        title: 'Configurar Líneas',
        content: `
            <p>Permite ajustar la capacidad de las líneas de producción y registrar paradas programadas (bloqueos por mantenimiento, feriados, etc.).</p>
        `
    },
    {
        selector: '#accordionIssues',
        title: 'Panel de Issues (Problemas)',
        content: `
            <p>Aquí aparecen las órdenes que el sistema <strong>no pudo planificar automáticamente</strong> o que tienen problemas graves (ej: fecha meta vencida).</p>
            <ul>
                <li><strong>Re-Planificar:</strong> Abre un asistente para corregir la orden manualmente.</li>
                <li><strong>Aceptar:</strong> Quita el aviso si usted decide que el retraso es aceptable.</li>
            </ul>
        `
    },
    {
        selector: '#accordionSemanal',
        title: 'Planificación Semanal - Vista Detallada',
        content: `
            <p><strong>Vista de Calendario</strong></p>
            <p>Muestra las órdenes de producción distribuidas en la semana actual. Cada columna representa un día.</p>
            <ul>
                <li>Puede ver qué órdenes están asignadas a cada día.</li>
                <li>Si hace clic en una tarjeta de orden, verá más detalles.</li>
                <li>Puede re-planificar órdenes haciendo clic en el botón correspondiente dentro de la tarjeta.</li>
            </ul>
        `
    },
    {
        selector: '#semanal-crp-tab',
        title: 'Pestaña: Planificación Semanal y CRP',
        content: `
            <p>Esta es la vista principal operativa.</p>
            <ul>
                <li><strong>Vista Detallada:</strong> Muestra el calendario día a día con las tarjetas de las órdenes.</li>
                <li><strong>CRP (Capacidad):</strong> Muestra gráficas de carga vs. capacidad para evitar cuellos de botella.</li>
            </ul>
        `
    },
    {
        selector: '#maestro-tab',
        title: 'Pestaña: Plan Maestro (Pendientes)',
        content: `
            <p>Listado de todas las órdenes que <strong>aún no tienen fecha asignada</strong> (Backlog).</p>
            <p>Desde aquí puede arrastrar o seleccionar órdenes para pasarlas al calendario semanal.</p>
        `
    },
    {
        selector: '#accordionCRP',
        title: 'Análisis CRP',
        content: `
            <p><strong>Capacity Requirements Planning</strong></p>
            <p>Esta tabla le dice si una línea está sobrecargada (rojo) o subutilizada (gris) en un día específico.</p>
            <p><em>Regla de oro:</em> Trate de mantener la utilización debajo del 85% (verde) para tener margen de maniobra.</p>
        `
    },
    {
        selector: '#notificationOffcanvas',
        title: 'Notificaciones',
        content: `
            <p>Muestra avisos importantes sobre la planificación, como reprogramaciones automáticas.</p>
        `
    }
];

let isHelpModeActive = false;

document.addEventListener('DOMContentLoaded', function() {
    // Buscar el botón de ayuda en la barra de herramientas (será inyectado o ya existente en HTML)
});

/**
 * Activa o desactiva el modo ayuda.
 */
function toggleHelpMode() {
    isHelpModeActive = !isHelpModeActive;
    const btnAyuda = document.getElementById('btn-toggle-help');
    
    if (isHelpModeActive) {
        document.body.classList.add('help-mode-active');
        if (btnAyuda) {
            btnAyuda.classList.replace('btn-outline-info', 'btn-info');
            btnAyuda.innerHTML = '<i class="bi bi-x-circle-fill me-1"></i> Cerrar Ayuda';
        }
        showHelpBadges();
    } else {
        document.body.classList.remove('help-mode-active');
        if (btnAyuda) {
            btnAyuda.classList.replace('btn-info', 'btn-outline-info');
            btnAyuda.innerHTML = '<i class="bi bi-question-circle-fill me-1"></i> Ayuda';
        }
        hideHelpBadges();
    }
}

/**
 * Inyecta los botones de interrogación (?) en la interfaz.
 */
function showHelpBadges() {
    helpData.forEach(item => {
        const targetEl = document.querySelector(item.selector);
        if (targetEl) {
            // Verificar si ya tiene badge
            const existingBadge = document.querySelector(`.help-badge[data-target-selector="${item.selector}"]`);
            if (existingBadge) return;

            // Crear el badge
            const badge = document.createElement('button');
            badge.className = 'btn btn-sm btn-info rounded-circle help-badge shadow-sm';
            badge.innerHTML = '<i class="bi bi-question-lg text-white"></i>';
            badge.style.position = 'absolute';
            // CORRECCION Z-INDEX: Los offcanvas de Bootstrap tienen z-index 1045, 
            // pero el botón que los abre está debajo.
            // La imagen muestra un z-index alto que hace que el badge "traspase" el offcanvas.
            // Bajamos el z-index del badge para que el offcanvas lo tape.
            // Pero debe ser mayor que el contenido normal.
            badge.style.zIndex = '1000'; // Antes 1090. Offcanvas es ~1045.
            
            badge.style.width = '24px';
            badge.style.height = '24px';
            badge.style.padding = '0';
            badge.style.display = 'flex';
            badge.style.alignItems = 'center';
            badge.style.justifyContent = 'center';
            badge.dataset.isHelpBadge = "true";
            badge.dataset.targetSelector = item.selector; 
            
            const tagName = targetEl.tagName.toLowerCase();
            const isVoidOrInteractive = ['input', 'img', 'br', 'hr', 'button', 'a'].includes(tagName);

            // CASO ESPECIAL: Si es el botón que abre el offcanvas (notificaciones), necesitamos lógica especial.
            // El selector '#notificationOffcanvas' apunta al PANEL oculto, no al botón.
            // El usuario quiere el badge en el botón que lo ABRE.
            // Así que si el selector es el offcanvas, buscamos su trigger.
            
            let finalTargetEl = targetEl;
            let insertMode = 'child'; // 'child' or 'sibling'
            
            if (item.selector === '#notificationOffcanvas') {
                // Buscar el botón que abre este offcanvas
                const triggerBtn = document.querySelector(`[data-bs-target="${item.selector}"]`);
                if (triggerBtn) {
                    finalTargetEl = triggerBtn;
                    insertMode = 'sibling'; // Es un botón, usamos la lógica de 'sibling' (padre relative)
                } else {
                    return; // No encontramos el botón, abortar.
                }
            } else if (isVoidOrInteractive) {
                insertMode = 'sibling';
            }

            if (insertMode === 'sibling') {
                // Insertar en el PADRE
                const parent = finalTargetEl.parentElement;
                
                const parentStyle = window.getComputedStyle(parent);
                if (parentStyle.position === 'static') {
                    parent.style.position = 'relative';
                }

                // Calcular posición relativa al padre
                const badgeLeft = finalTargetEl.offsetLeft + finalTargetEl.offsetWidth - 10;
                const badgeTop = finalTargetEl.offsetTop - 10;

                badge.style.left = `${badgeLeft}px`;
                badge.style.top = `${badgeTop}px`;

                parent.appendChild(badge);

            } else {
                // Insertar ADENTRO (contenedores)
                const targetStyle = window.getComputedStyle(finalTargetEl);
                if (targetStyle.position === 'static') {
                    finalTargetEl.style.position = 'relative';
                }
                
                badge.style.top = '-10px';
                badge.style.right = '-10px';

                finalTargetEl.appendChild(badge);
            }
            
            badge.onclick = (e) => {
                e.stopPropagation();
                e.preventDefault();
                openHelpModal(item.title, item.content);
            };
        }
    });
}

/**
 * Elimina los badges.
 */
function hideHelpBadges() {
    const badges = document.querySelectorAll('.help-badge');
    badges.forEach(b => b.remove());
}

/**
 * Abre el modal de ayuda.
 */
function openHelpModal(title, content) {
    const modalEl = document.getElementById('helpModal');
    if (!modalEl) return;

    document.getElementById('helpModalTitle').textContent = title;
    document.getElementById('helpModalBody').innerHTML = content;

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}
