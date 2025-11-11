document.addEventListener('DOMContentLoaded', function () {
    // --- Lógica para el botón de expandir/colapsar ---
    const expandButtons = document.querySelectorAll('.btn-expand');
    expandButtons.forEach(button => {
        const targetId = button.getAttribute('data-bs-target');
        const collapseElement = document.querySelector(targetId);
        const icon = button.querySelector('i');

        if (collapseElement) {
            collapseElement.addEventListener('show.bs.collapse', function () {
                icon.classList.remove('bi-chevron-right');
                icon.classList.add('bi-chevron-down');
            });

            collapseElement.addEventListener('hide.bs.collapse', function () {
                icon.classList.remove('bi-chevron-down');
                icon.classList.add('bi-chevron-right');
            });
        }
    });

    // --- Manejador para el modal MARCAR COMO NO APTO ---
    var modalNoApto = document.getElementById('modalNoApto');
    if (modalNoApto) {
        modalNoApto.addEventListener('show.bs.modal', function (event) {
            var button = event.relatedTarget;
            var loteId = button.getAttribute('data-lote-id');
            var loteNumero = button.getAttribute('data-lote-numero');
            
            var form = modalNoApto.querySelector('#formNoApto');
            // Construir la URL dinámicamente. 
            // Asumimos una estructura de URL /lotes/<lote_id>/no-apto
            var actionUrl = `/inventario/lote/${loteId}/marcar-no-apto`; 
            form.setAttribute('action', actionUrl);
            
            modalNoApto.querySelector('#loteNumeroNoApto').textContent = loteNumero;
        });

        var formNoApto = document.getElementById('formNoApto');
        if (formNoApto) {
            formNoApto.addEventListener('submit', function() {
                var submitButton = formNoApto.querySelector('button[type="submit"]');
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Confirmando...';
            });
        }
    }
});
