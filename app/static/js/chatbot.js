document.addEventListener('DOMContentLoaded', function () {
    const chatbotIcon = document.getElementById('chatbot-icon');
    const chatbotWindow = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close-btn');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotOptions = document.getElementById('chatbot-options');

    let knowledgeBase = []; // Ahora será un array de objetos

    // Cargar las preguntas y respuestas desde la API al iniciar
    async function loadKnowledgeBase() {
        try {
            const response = await fetch('/api/chatbot/qas');
            if (!response.ok) {
                throw new Error('No se pudieron cargar las preguntas y respuestas.');
            }
            const result = await response.json();
            if (result.success && Array.isArray(result.data)) {
                // Guardamos el array completo
                knowledgeBase = result.data;
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
        
        if (knowledgeBase.length === 0) {
            addMessage('No hay preguntas frecuentes disponibles en este momento.', 'bot');
            chatbotOptions.innerHTML = '';
            return;
        }

        showOptions(knowledgeBase);
    }

    function showOptions(options) {
        chatbotOptions.innerHTML = '';
        options.forEach(qa => {
            const button = document.createElement('button');
            button.classList.add('chatbot-option-btn');
            button.textContent = qa.pregunta;
            button.addEventListener('click', () => handleOptionClick(qa));
            chatbotOptions.appendChild(button);
        });
    }

    async function handleOptionClick(qa) {
        addMessage(qa.pregunta, 'user');
        chatbotOptions.innerHTML = ''; // Limpiar opciones inmediatamente

        // Lógica de redirección
        if (qa.type === 'redirect' && qa.url) {
            setTimeout(() => {
                addMessage(qa.respuesta, 'bot');
                setTimeout(() => window.location.href = qa.url, 1000);
            }, 500);
            return;
        }

        // Mostrar respuesta y buscar sub-preguntas
        setTimeout(async () => {
            addMessage(qa.respuesta, 'bot');
            
            try {
                const response = await fetch(`/api/chatbot/qas/${qa.id}/children`);
                const result = await response.json();

                if (result.success && result.data.length > 0) {
                    showOptions(result.data);
                }
                // Siempre añadir la opción de volver al menú principal
                showReturnMenuOption(true);

            } catch (error) {
                console.error('Error al cargar sub-preguntas:', error);
                showReturnMenuOption();
            }
        }, 500);
    }

    function showReturnMenuOption(append = false) {
        if (!append) {
            chatbotOptions.innerHTML = '';
        }
        const returnButton = document.createElement('button');
        returnButton.classList.add('chatbot-option-btn', 'return-btn');
        returnButton.textContent = 'Volver al menú principal';
        returnButton.addEventListener('click', showInitialOptions);
        chatbotOptions.appendChild(returnButton);
    }

    // Cargar los datos al iniciar y luego mostrar las opciones
    loadKnowledgeBase().then(() => {
        showInitialOptions();
    });
});
