document.addEventListener('DOMContentLoaded', function () {
    const fixedTopValue = '80px'; 
    const scrollActivationPoint = 110; 
    const panels = document.querySelectorAll('.fixed-side-panel');

    // Si no hay paneles, no hacer nada
    if (panels.length === 0) {
        return;
    }
    
    function initializeFixedPanel(sidePanel) {
        const parentCol = sidePanel.closest('.col-lg-4');
        if (!parentCol) return; 

        const contentCol = parentCol.parentNode.querySelector('.col-lg-8');
        if (!contentCol) return;

        const referenceElement = contentCol.querySelector('.card, .d-flex, h1');
        if (!referenceElement) return;

        let initialOffsetTop = 0;

        function setInitialAbsolutePosition() {
            // Asegurarnos de que el CSS se renderice primero
            setTimeout(() => {
                // Solo calculamos si estamos en modo no-fijo (absolute)
                // Usamos getComputedStyle para leer el estilo que aplicó el CSS
                if (window.getComputedStyle(sidePanel).position === 'absolute') {
                    initialOffsetTop = referenceElement.offsetTop;
                    sidePanel.style.top = initialOffsetTop + 'px';
                }
            }, 100); // Dar tiempo al renderizado
        }

        // Solo calcular la posición inicial si estamos en desktop
        if (window.innerWidth >= 992) {
            setInitialAbsolutePosition();
        }

        function handleScroll() {
            // FIX: No ejecutar la lógica de scroll si la ventana es pequeña
            // La media query de CSS en styles.css (max-width: 991px) se encargará de esto
            if (window.innerWidth < 992) {
                // Asegurarse de limpiar estilos fijos si la ventana se achica
                sidePanel.style.position = ''; // Dejar que CSS controle
                sidePanel.style.top = ''; // Dejar que CSS controle
                return; 
            }

            // Si estamos en pantalla grande, aplicar lógica de scroll
            sidePanel.style.transition = 'none'; 

            if (window.scrollY > scrollActivationPoint) {
                sidePanel.style.position = 'fixed';
                sidePanel.style.top = fixedTopValue;
            } else {
                sidePanel.style.position = 'absolute';
                // Usamos el offset inicial calculado
                sidePanel.style.top = (initialOffsetTop > 0 ? initialOffsetTop : referenceElement.offsetTop) + 'px';
            }
            
            setTimeout(() => {
                sidePanel.style.transition = ''; 
            }, 50);
        }
        
        window.addEventListener('scroll', handleScroll, { passive: true });
        
        // FIX: Recalcular al cambiar tamaño
        window.addEventListener('resize', () => {
             if (window.innerWidth >= 992) {
                // Si volvemos a desktop, recalcular posición
                setInitialAbsolutePosition();
             } else {
                // Limpiar estilos en resize a móvil
                sidePanel.style.position = '';
                sidePanel.style.top = '';
             }
        });
    }
    
    panels.forEach(initializeFixedPanel);
});