import os
import threading
from app import create_app
#from pymodbus.server import StartTcpServer as SimpleServer
from app.config import Config

# 🧵 FUNCIÓN PARA INICIAR EL SERVIDOR MODBUS
# La dependencia ModSlaveService no existe, por lo que se deshabilita la funcionalidad.
def iniciar_modbus():
     try:
         # La clase ModSlaveService no está definida en el proyecto.
        # t = SimpleServer(ModSlaveService, port=18861, auto_register=False)
        print("🟢 Servidor Modbus iniciado en puerto 18861 (funcionalidad deshabilitada)")
         # t.start()
     except OSError as e:
         print(f"⚠️ Error al iniciar Modbus: {e}")
         if "10048" in str(e):
             print("🔌 El puerto 18861 ya está en uso. Verifica si otro proceso lo está ocupando.")
     except Exception as e:
         print(f"❌ Error inesperado en servidor Modbus: {e}")

# 🧱 INICIALIZAR FLASK
# Utiliza la fábrica de app/__init__.py, que está orientada a la API.
app = create_app()

if __name__ == "__main__":
    print("🚀 Iniciando Servidor de Desarrollo...")
    print(f"🔧 Modo Debug: {Config.DEBUG}")

    # 🧵 Iniciar servidor Modbus solo si no es reinicio por Flask
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(target=iniciar_modbus, daemon=True).start()

    # 🌐 Ejecutar Flask sin reloader para evitar doble ejecución
    flask_port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=flask_port, debug=Config.DEBUG, use_reloader=False)