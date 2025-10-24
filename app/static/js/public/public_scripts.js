document.addEventListener('DOMContentLoaded', function() {
    
    // --- 1. Script de Navbar con Scroll ---
    const nav = document.querySelector('.main-nav');
    if (nav) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        });
    }

    // --- 2. Script Menú Hamburguesa (Corregido) ---
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links'); // El contenedor de links

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', function() {
            // Animación del botón "X"
            navToggle.classList.toggle('active'); 
            // Muestra/oculta el menú
            navLinks.classList.toggle('active'); 
        });
    }

    // --- 3. Animación al scroll (Intersection Observer) ---
    // Selecciona elementos a animar
    const animatedElements = document.querySelectorAll('.feature-card, .jumbotron > *, .about-card, .value-item, h1, h2, p'); 

    // Pausar animación hasta que sea visible (si usas la animación 'fadeIn' en el CSS)
    animatedElements.forEach((el) => {
         el.style.animationPlayState = 'paused';
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running'; // Inicia la animación CSS
                observer.unobserve(entry.target); // Deja de observar una vez animado
            }
        });
    }, { threshold: 0.1 }); // Animar cuando al menos 10% sea visible

    animatedElements.forEach((el) => {
        observer.observe(el);
    });

});