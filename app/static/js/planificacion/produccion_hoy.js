        function openModal(modalId) {
            document.getElementById(modalId).classList.add('active');
        }

        function closeModal() {
            document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        }

        function startOrder(btn) {
            openModal('startModal');
        }

        function confirmStart() {
            closeModal();
            showNotification('✅ Orden iniciada correctamente', 'success');
        }

        function pauseOrder() {
            openModal('pauseModal');
        }

        function confirmPause() {
            closeModal();
            showNotification('⏸️ Orden pausada. Tiempo de inactividad registrado.', 'warning');
        }

        function reportProgress() {
            openModal('reportModal');
        }

        function submitReport() {
            closeModal();
            showNotification('📊 Avance reportado exitosamente', 'success');
        }

        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${type === 'success' ? '#10b981' : '#f59e0b'};
                color: white;
                padding: 14px 20px;
                border-radius: 8px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                z-index: 2000;
                font-weight: 500;
                font-size: 14px;
                animation: slideIn 0.3s ease;
            `;
            notification.textContent = message;
            document.body.appendChild(notification);

            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }

        // Cerrar modal al hacer clic fuera
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) closeModal();
            });
        });

        // Filtros
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            });
        });

        // Animaciones CSS
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(400px);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);