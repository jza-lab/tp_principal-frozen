self.addEventListener('install', (event) => {
    console.log('Service Worker: Installed');
});

self.addEventListener('fetch', (event) => {
    // Network-only strategy for PWA installation support without offline capability
    event.respondWith(fetch(event.request));
});