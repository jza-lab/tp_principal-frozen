document.addEventListener('DOMContentLoaded', function () {
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
});
