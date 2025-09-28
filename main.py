import os
import threading
from app import create_app
#from pymodbus.server import StartTcpServer as SimpleServer
from app.config import Config

# 🔧 IMPORTACIÓN DEL SERVIDOR MODBUS
# Si usás rpyc:
#from rpyc.utils.server import ThreadedServer as SimpleServer

# 🧱 INICIALIZAR FLASK
# Utiliza la fábrica de app/__init__.py, que está orientada a la API.
app = create_app()

if __name__ == "__main__":
    print("🚀 Iniciando Servidor de Desarrollo...")
    print(f"🔧 Modo Debug: {Config.DEBUG}")


    # 🌐 Ejecutar Flask sin reloader para evitar doble ejecución
    flask_port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=flask_port, debug=True)


