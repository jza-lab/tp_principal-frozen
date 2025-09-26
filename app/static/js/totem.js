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
        
        // Aquí se haría la llamada fetch al backend para el reconocimiento facial
        // fetch('/totem/fichar', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify({ tipo: tipo, imagen: imageData })
        // })
        // .then(response => response.json())
        // .then(data => {
        //     if (data.success) {
        //         alert(`Fichaje de ${tipo} exitoso para ${data.empleado}`);
        //     } else {
        //         alert(`Error en el fichaje: ${data.message}`);
        //     }
        // })
        // .catch(error => {
        //     console.error('Error en el fichaje:', error);
        //     alert('Ocurrió un error al intentar fichar.');
        // });

        // Simulación para desarrollo sin backend real
        alert(`(Simulación) Fichaje de ${tipo} realizado. La integración con el backend está pendiente.`);
    }

    botonEntrada.addEventListener('click', () => {
        fichar('entrada');
    });

    botonSalida.addEventListener('click', () => {
        fichar('salida');
    });
});