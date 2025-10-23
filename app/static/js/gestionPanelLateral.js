document.addEventListener('DOMContentLoaded', function () {
    const fixedTopValue = '80px'; 
    const scrollActivationPoint = 110; 
    const panels = document.querySelectorAll('.fixed-side-panel');

    if (panels.length === 0 || window.innerWidth < 992) {
        return;
    }
    
    function initializeFixedPanel(sidePanel) {
        const parentCol = sidePanel.closest('.col-lg-4');
        if (!parentCol) return; 

        const contentCol = parentCol.parentNode.querySelector('.col-lg-8');
        if (!contentCol) return;

        const referenceElement = contentCol.querySelector('.card, .d-flex, h1');
        if (!referenceElement) return;

        function setInitialAbsolutePosition() {
            sidePanel.style.position = 'absolute';
            sidePanel.style.top = referenceElement.offsetTop + 'px';
        }

        setInitialAbsolutePosition();

        function handleScroll() {
            sidePanel.style.transition = 'none'; 

            if (window.scrollY > scrollActivationPoint) {
                sidePanel.style.position = 'fixed';
                sidePanel.style.top = fixedTopValue;
            } else {
                sidePanel.style.position = 'absolute';
                sidePanel.style.top = referenceElement.offsetTop + 'px';
            }
            setTimeout(() => {
                sidePanel.style.transition = ''; 
            }, 50);
        }
        window.addEventListener('scroll', handleScroll);
    }
    
    function checkSizeAndApplyFix() {
        if (window.innerWidth < 992) {
            panels.forEach(p => {
                p.style.position = 'relative'; 
                p.style.top = 'auto';
                window.removeEventListener('scroll', initializeFixedPanel(p)); 
            });
            return;
        }
        panels.forEach(p => initializeFixedPanel(p));
    }

    panels.forEach(initializeFixedPanel);
    window.addEventListener('resize', checkSizeAndApplyFix);

});