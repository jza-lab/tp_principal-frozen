/**
 * Módulo interactiveSelectors.js
 * 
 * Gestiona la lógica de los selectores de tarjetas (roles, turnos, sectores)
 * para los formularios de usuario. Es reutilizable tanto en la creación como
 * en la edición de perfiles.
 */

// --- Estado y Configuración ---

let selectedRole = null;
let selectedTurno = null;
let selectedSectores = [];
const MAX_SECTORES = 2;

// --- Funciones de Inicialización ---

/**
 * Inicializa los selectores de tarjetas para roles, turnos y sectores.
 * @param {object} initialState - Estado inicial con los IDs seleccionados.
 * @param {number|null} initialState.role_id - ID del rol seleccionado.
 * @param {number|null} initialState.turno_id - ID del turno seleccionado.
 * @param {Array<number>} initialState.sectores_ids - Array de IDs de sectores seleccionados.
 */
export function initializeSelectors(initialState = {}) {
    selectedRole = initialState.role_id || null;
    selectedTurno = initialState.turno_id || null;
    selectedSectores = initialState.sectores_ids || [];

    initRoleSelector();
    initTurnoSelector();
    initSectorSelector();
}

// --- Lógica del Selector de Roles ---

function initRoleSelector() {
    const rolCards = document.querySelectorAll('.rol-card');
    const rolInput = document.getElementById('role_id');
    
    // Marcar el rol inicial si existe
    if (selectedRole) {
        rolCards.forEach(card => {
            if (parseInt(card.dataset.rolId) === selectedRole) {
                card.classList.add('selected');
            }
        });
    }

    rolCards.forEach(card => {
        card.addEventListener('click', () => {
            if (card.closest('.profile-content.view-mode')) return;
            rolCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedRole = parseInt(card.dataset.rolId);
            if (rolInput) rolInput.value = selectedRole;
            
            // Disparar un evento para que otros scripts puedan reaccionar
            card.dispatchEvent(new Event('selectionChanged', { bubbles: true }));
        });
    });
}

// --- Lógica del Selector de Turnos ---

function initTurnoSelector() {
    const turnoCards = document.querySelectorAll('.turno-card');
    const turnoInput = document.getElementById('turno_id');

    // Marcar el turno inicial si existe
    if (selectedTurno) {
        turnoCards.forEach(card => {
            if (parseInt(card.dataset.turnoId) === selectedTurno) {
                card.classList.add('selected');
            }
        });
    }

    turnoCards.forEach(card => {
        card.addEventListener('click', () => {
            if (card.closest('.profile-content.view-mode')) return;
            turnoCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedTurno = parseInt(card.dataset.turnoId);
            if (turnoInput) turnoInput.value = selectedTurno;
             
            card.dispatchEvent(new Event('selectionChanged', { bubbles: true }));
        });
    });
}

// --- Lógica del Selector de Sectores ---
function initSectorSelector() {
    const sectorCards = document.querySelectorAll('.sector-card');
    const sectoresInput = document.getElementById('sectores');

    // Marcar sectores iniciales y popular el input
    if (selectedSectores.length > 0) {
        sectorCards.forEach(card => {
            if (selectedSectores.includes(parseInt(card.dataset.sectorId))) {
                card.classList.add('selected');
            }
        });
    }
    if (sectoresInput) {
        sectoresInput.value = JSON.stringify(selectedSectores);
    }
    updateSectoresUI();

    sectorCards.forEach(card => {
        card.addEventListener('click', () => {
            if (card.closest('.profile-content.view-mode') || card.classList.contains('disabled')) return;

            const sectorId = parseInt(card.dataset.sectorId);
            const isSelected = card.classList.toggle('selected');

            if (isSelected) {
                if (selectedSectores.length < MAX_SECTORES) {
                    selectedSectores.push(sectorId);
                } else {
                    card.classList.remove('selected'); // Revertir si se excede el límite
                    // Opcional: mostrar notificación
                }
            } else {
                selectedSectores = selectedSectores.filter(id => id !== sectorId);
            }
            
            if (sectoresInput) sectoresInput.value = JSON.stringify(selectedSectores);
            updateSectoresUI();
            card.dispatchEvent(new Event('selectionChanged', { bubbles: true }));
        });
    });
}

function updateSectoresUI() {
    const sectorCards = document.querySelectorAll('.sector-card');
    const counterText = document.getElementById('counterText');

    // Actualizar contador
    if (counterText) {
        counterText.textContent = `${selectedSectores.length}/${MAX_SECTORES}`;
    }

    // Actualizar badges de orden y estado disabled
    sectorCards.forEach(card => {
        const sectorId = parseInt(card.dataset.sectorId);
        const badge = card.querySelector('.sector-badge');

        if (selectedSectores.includes(sectorId)) {
            const order = selectedSectores.indexOf(sectorId) + 1;
            if (badge) badge.textContent = order;
        }

        if (selectedSectores.length >= MAX_SECTORES && !card.classList.contains('selected')) {
            card.classList.add('disabled');
        } else {
            card.classList.remove('disabled');
        }
    });
}

// --- Funciones para obtener el estado actual ---
export function getSelectorsState() {
    return {
        role_id: selectedRole,
        turno_id: selectedTurno,
        sectores: selectedSectores
    };
}