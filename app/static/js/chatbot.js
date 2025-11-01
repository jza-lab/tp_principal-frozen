document.addEventListener('DOMContentLoaded', function () {
    const chatbotIcon = document.getElementById('chatbot-icon');
    const chatbotWindow = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close-btn');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotOptions = document.getElementById('chatbot-options');

    // Base de conocimientos de preguntas y respuestas
    const knowledgeBase = {
        "Crear una cuenta": "Para crear una cuenta, haz clic en 'Login' en la esquina superior derecha y luego selecciona 'Registrarse'.",
        "Métodos de pago": "Aceptamos tarjetas de crédito y débito (Visa, MasterCard) y transferencias bancarias.",
        "Hacer un pedido": "Para hacer un pedido, inicia sesión, añade productos a tu carrito y sigue los pasos para finalizar la compra.",
        "Ver mis pedidos": "Puedes ver el historial de tus pedidos en tu perfil, en la sección 'Mis Pedidos'.",
        "Costo de envío": "El costo de envío depende de tu ubicación y se calcula automáticamente durante la compra."
    };

    // Mostrar/ocultar la ventana del chatbot
    chatbotIcon.addEventListener('click', () => {
        chatbotWindow.style.display = 'flex';
        showInitialOptions();
    });

    closeBtn.addEventListener('click', () => {
        chatbotWindow.style.display = 'none';
    });

    function addMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chatbot-message', sender);
        messageElement.textContent = text;
        chatbotMessages.appendChild(messageElement);
        // Scroll automático al último mensaje
        chatbotMessages.parentElement.scrollTop = chatbotMessages.parentElement.scrollHeight;
    }

    function showInitialOptions() {
        // Limpiar mensajes anteriores, excepto el saludo inicial
        chatbotMessages.innerHTML = '<div class="chatbot-message bot">¡Hola! Soy tu asistente virtual. Selecciona una opción para ayudarte:</div>';
        // Limpiar opciones anteriores
        chatbotOptions.innerHTML = '';

        // Crear y añadir botones de opciones
        for (const question in knowledgeBase) {
            const button = document.createElement('button');
            button.classList.add('chatbot-option-btn');
            button.textContent = question;
            button.addEventListener('click', () => handleOptionClick(question));
            chatbotOptions.appendChild(button);
        }
    }

    function handleOptionClick(question) {
        const answer = knowledgeBase[question];

        // Añadir la pregunta del usuario y la respuesta del bot
        addMessage(question, 'user');
        setTimeout(() => {
            addMessage(answer, 'bot');
            // Después de la respuesta, ofrecer volver al menú principal
            showReturnMenuOption();
        }, 500);

        // Ocultar las opciones actuales
        chatbotOptions.innerHTML = '';
    }

    function showReturnMenuOption() {
        chatbotOptions.innerHTML = ''; // Limpiar opciones
        const returnButton = document.createElement('button');
        returnButton.classList.add('chatbot-option-btn');
        returnButton.textContent = 'Volver al menú principal';
        returnButton.addEventListener('click', showInitialOptions);
        chatbotOptions.appendChild(returnButton);
    }

    // Mostrar las opciones iniciales al cargar
    showInitialOptions();
});
