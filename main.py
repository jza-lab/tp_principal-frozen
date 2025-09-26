import os
import threading
from app import create_app
from app.config import Config

# 🔧 IMPORTACIÓN DEL SERVIDOR MODBUS
# Si usás rpyc:
from rpyc.utils.server import ThreadedServer as SimpleServer

# 🧵 FUNCIÓN PARA INICIAR EL SERVIDOR MODBUS
def iniciar_modbus():
    try:
        t = SimpleServer(ModSlaveService, port=18861, auto_register=False)
        print("🟢 Servidor Modbus iniciado en puerto 18861")
        t.start()
    except OSError as e:
        print(f"⚠️ Error al iniciar Modbus: {e}")
        if "10048" in str(e):
            print("🔌 El puerto 18861 ya está en uso. Verifica si otro proceso lo está ocupando.")
    except Exception as e:
        print(f"❌ Error inesperado en servidor Modbus: {e}")

# 🧱 INICIALIZAR FLASK
app = create_app()

if __name__ == "__main__":
    print("🚀 Iniciando API de Trazabilidad de Insumos...")
    print(f"🔧 Modo Debug: {Config.DEBUG}")
    print(f"🔗 Supabase URL: {Config.SUPABASE_URL}")
    print("📌 Endpoints disponibles:")
    print("    GET  /api/health")
    print("    GET  /api/insumos/catalogo")
    print("    POST /api/insumos/catalogo")
    print("    GET  /api/inventario/lotes")
    print("    POST /api/inventario/lotes")
    print("    POST /api/inventario/alertas")

    # 🧵 Iniciar servidor Modbus solo si no es reinicio por Flask
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(target=iniciar_modbus, daemon=True).start()

    # 🌐 Ejecutar Flask sin reloader para evitar doble ejecución
    flask_port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=flask_port, debug=Config.DEBUG, use_reloader=False)


