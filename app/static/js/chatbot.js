document.addEventListener('DOMContentLoaded', function () {
    const chatbotIcon = document.getElementById('chatbot-icon');
    const chatbotWindow = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close-btn');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotOptions = document.getElementById('chatbot-options');

    let knowledgeBase = {}; // Ahora será un objeto que se cargará desde la API

    // Cargar las preguntas y respuestas desde la API al iniciar
    async function loadKnowledgeBase() {
        try {
            const response = await fetch('/api/chatbot/qas');
            if (!response.ok) {
                throw new Error('No se pudieron cargar las preguntas y respuestas.');
            }
            const result = await response.json();
            if (result.success && Array.isArray(result.data)) {
                // Transformar el array en un objeto para fácil acceso
                knowledgeBase = result.data.reduce((acc, qa) => {
                    acc[qa.pregunta] = qa.respuesta;
                    return acc;
                }, {});
            }
        } catch (error) {
            console.error('Error al cargar la base de conocimientos:', error);
            // Mensaje de error en el chat si la API falla
            addMessage('Lo siento, no estoy disponible en este momento. Inténtalo más tarde.', 'bot');
        }
    }

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
        chatbotMessages.innerHTML = '<div class="chatbot-message bot">¡Hola! Soy tu asistente virtual. Selecciona una opción para ayudarte:</div>';
        chatbotOptions.innerHTML = '';

        if (Object.keys(knowledgeBase).length === 0) {
            addMessage('No hay preguntas frecuentes disponibles en este momento.', 'bot');
            return;
        }

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
        addMessage(question, 'user');
        
        setTimeout(() => {
            addMessage(answer, 'bot');
            showReturnMenuOption();
        }, 500);

        chatbotOptions.innerHTML = '';
    }

    function showReturnMenuOption() {
        chatbotOptions.innerHTML = '';
        const returnButton = document.createElement('button');
        returnButton.classList.add('chatbot-option-btn');
        returnButton.textContent = 'Volver al menú principal';
        returnButton.addEventListener('click', showInitialOptions);
        chatbotOptions.appendChild(returnButton);
    }

    // Cargar los datos al iniciar y luego mostrar las opciones
    loadKnowledgeBase().then(() => {
        showInitialOptions();
    });
});
