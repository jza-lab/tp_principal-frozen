    document.addEventListener('DOMContentLoaded', function () {
        // Variables globales
        const searchInput = document.getElementById('searchInput');
        const estadoBtns = document.querySelectorAll('.btn-filter-estado');
        const quickActionBtns = document.querySelectorAll('.btn-quick-action');
        const ordenCards = document.querySelectorAll('.orden-card');
        const btnClearAll = document.getElementById('btnClearAll');
        const visibleCountEl = document.getElementById('visibleCount');
        const totalCountEl = document.getElementById('totalCount');
        const ordenesContainer = document.getElementById('ordenesContainer');
        const noResultsMessage = document.getElementById('noResultsMessage');

        // Usuario actual (deberías obtenerlo del backend)
        const currentUser = "{{ current_user.username if current_user else '' }}";

        let activeFilters = {
            estado: '',
            search: '',
            quickFilter: ''
        };

        // Total de órdenes
        const totalOrdenes = ordenCards.length;
        totalCountEl.textContent = totalOrdenes;

        // Función principal de filtrado
        function applyFilters() {
            let visibleCount = 0;

            ordenCards.forEach(card => {
                let show = true;

                // Filtro por estado
                if (activeFilters.estado && card.dataset.estado !== activeFilters.estado) {
                    show = false;
                }

                // Filtro por búsqueda de código
                if (activeFilters.search) {
                    const codigo = card.dataset.codigo.toLowerCase();
                    const searchTerm = activeFilters.search.toLowerCase();
                    if (!codigo.includes(searchTerm)) {
                        show = false;
                    }
                }

                // Filtro rápido por fecha
                if (activeFilters.quickFilter) {
                    const fecha = new Date(card.dataset.fecha);
                    const hoy = new Date();
                    hoy.setHours(0, 0, 0, 0);

                    switch (activeFilters.quickFilter) {
                        case 'mis-ordenes':
                            if (card.dataset.creador !== currentUser) {
                                show = false;
                            }
                            break;
                        case 'hoy':
                            const fechaCard = new Date(fecha);
                            fechaCard.setHours(0, 0, 0, 0);
                            if (fechaCard.getTime() !== hoy.getTime()) {
                                show = false;
                            }
                            break;
                        case 'ultimos-7':
                            const hace7 = new Date(hoy);
                            hace7.setDate(hace7.getDate() - 7);
                            if (fecha < hace7) {
                                show = false;
                            }
                            break;
                        case 'ultimos-30':
                            const hace30 = new Date(hoy);
                            hace30.setDate(hace30.getDate() - 30);
                            if (fecha < hace30) {
                                show = false;
                            }
                            break;
                    }
                }

                // Mostrar u ocultar
                if (show) {
                    card.classList.remove('hidden');
                    visibleCount++;
                } else {
                    card.classList.add('hidden');
                }
            });

            // Actualizar contador
            visibleCountEl.textContent = visibleCount;

            // Mostrar mensaje si no hay resultados
            if (visibleCount === 0) {
                ordenesContainer.style.display = 'none';
                noResultsMessage.style.display = 'block';
            } else {
                ordenesContainer.style.display = 'flex';
                noResultsMessage.style.display = 'none';
            }

            // Mostrar/ocultar botón de limpiar filtros
            const hasActiveFilters = activeFilters.estado || activeFilters.search || activeFilters.quickFilter;
            btnClearAll.style.display = hasActiveFilters ? 'block' : 'none';
        }

        // Event listeners para botones de estado
        estadoBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                // Remover active de todos
                estadoBtns.forEach(b => b.classList.remove('active'));
                
                // Activar el clickeado
                this.classList.add('active');
                
                // Actualizar filtro
                activeFilters.estado = this.dataset.estado;
                
                applyFilters();
            });
        });

        // Event listener para búsqueda
        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                activeFilters.search = this.value.trim();
                applyFilters();
            }, 300); // Debounce de 300ms
        });

        // Event listeners para filtros rápidos
        quickActionBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                const filter = this.dataset.quickFilter;
                
                // Toggle active
                if (this.classList.contains('active')) {
                    this.classList.remove('active');
                    activeFilters.quickFilter = '';
                } else {
                    quickActionBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    activeFilters.quickFilter = filter;
                }
                
                applyFilters();
            });
        });

        // Limpiar todos los filtros
        btnClearAll.addEventListener('click', function () {
            // Resetear filtros
            activeFilters = {
                estado: '',
                search: '',
                quickFilter: ''
            };

            // Limpiar búsqueda
            searchInput.value = '';

            // Resetear botones de estado
            estadoBtns.forEach(b => b.classList.remove('active'));
            estadoBtns[0].classList.add('active'); // Activar "Todas"

            // Resetear filtros rápidos
            quickActionBtns.forEach(b => b.classList.remove('active'));

            applyFilters();
        });

        // Manejo de formularios de confirmación
        const forms = document.querySelectorAll('.confirm-form');
        forms.forEach(form => {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                const title = form.dataset.title || 'Confirmar Acción';
                const message = form.dataset.message || '¿Está seguro de que desea realizar esta acción?';
                const buttonType = form.dataset.buttonType || 'primary';

                showConfirmationModal(
                    title,
                    message,
                    () => {
                        form.submit();
                    },
                    buttonType
                );
            });
        });
    });