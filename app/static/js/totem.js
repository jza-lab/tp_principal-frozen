document.addEventListener('DOMContentLoaded', function () {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const botonEntrada = document.getElementById("botonEntrada");
    const botonSalida = document.getElementById("botonSalida");

    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(function (stream) {
            video.srcObject = stream;
            video.play();
        })
        .catch(function (err) {
            console.log("An error occurred! " + err);
            alert("No se pudo acceder a la cámara. Por favor, revise los permisos.");
        });

    function fichar(tipo) {
        // 1. Capturar imagen desde el video
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvas.toDataURL('image/jpeg');

        // 2. Enviar la imagen al backend (placeholder)
        console.log(`Enviando imagen para fichaje de ${tipo}`);
        
        // 2. Enviar la imagen al backend
        console.log(`Enviando imagen para fichaje de ${tipo}`);
        
        fetch('/asistencia/fichar-totem', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo: tipo, imagen: imageData })
        })
        .then(response => response.json())
        .then(data => {
            const guia = document.getElementById("guia");
            guia.textContent = data.message;
            if (data.success) {
                guia.style.color = 'green';
            } else {
                guia.style.color = 'red';
            }
            setTimeout(() => {
                guia.textContent = 'Por favor, mire a la cámara para fichar.';
                guia.style.color = '';
            }, 5000);
        })
        .catch(error => {
            console.error('Error en la llamada fetch:', error);
            const guia = document.getElementById("guia");
            guia.textContent = 'Error de conexión con el servidor.';
            guia.style.color = 'red';
            setTimeout(() => {
                guia.textContent = 'Por favor, mire a la cámara para fichar.';
                guia.style.color = '';
            }, 5000);
        });
    }

    botonEntrada.addEventListener('click', () => {
        fichar('entrada');
    });

    botonSalida.addEventListener('click', () => {
        fichar('salida');
    });
});