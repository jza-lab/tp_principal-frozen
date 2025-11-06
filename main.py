import os
from app import create_app
from app.config import Config

# Inicializar la aplicación Flask usando el factory
app = create_app()

if __name__ == "__main__":
    """
    Punto de entrada principal para ejecutar la aplicación Flask.
    """
    flask_port = int(os.environ.get("FLASK_PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=flask_port,
        debug=True,
        use_reloader=False,  # ⬅️ ESTA ES LA CLAVE
        threaded=False       # ⬅️ EVITA HILOS MÚLTIPLES
    )
