document.addEventListener('DOMContentLoaded', () => {
    const TRANSITION_DURATION = 300; 
    const links = document.querySelectorAll('a[href]:not([href^="#"]):not([href*="void(0)"]):not([target="_blank"]):not([data-notransition])');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            const currentPath = window.location.pathname;
            const newPath = this.pathname;

            if (currentPath === newPath) {
                return;
            }

            // Evita la navegación inmediata
            e.preventDefault(); 
            const newLocation = this.href;

            document.body.classList.add('fade-out'); 

            setTimeout(() => {
                window.location = newLocation;
            }, TRANSITION_DURATION); 
        });
    });
});
// Asegurarse de que el cuerpo sea visible al mostrar la página (incluyendo bfcache)
window.addEventListener('pageshow', function(event) {
    // Eliminar la clase 'fade-out' independientemente de si viene de caché o no
    document.body.classList.remove('fade-out');
    
    // Opcional: Log para saber si vino de bfcache
    if (event.persisted) {
        console.log('Page loaded from bfcache. Ensuring fade-out is removed.');
    } else {
        console.log('Page loaded normally. Ensuring fade-out is removed.');
    }
});