from flask import Blueprint, redirect, url_for, flash, session, request, jsonify, render_template
from app.services.asistencia_service import AsistenciaService
from app.repositories.asistencia_repository import AsistenciaRepository
from app.services.usuario_service import UsuarioService

asistencia_bp = Blueprint('asistencia', __name__, url_prefix='/asistencia')

# Inyección de dependencias
asistencia_repo = AsistenciaRepository()
asistencia_service = AsistenciaService(asistencia_repo)
usuario_service = UsuarioService()

@asistencia_bp.route('/registrar-entrada', methods=['POST'])
def registrar_entrada():
    """Registra la entrada del usuario logueado."""
    # TODO: Implementar lógica de verificación facial.
    # 1. Recibir la imagen del rostro desde request.form['facial_image']
    # 2. Obtener el encoding del usuario logueado desde la base de datos.
    # 3. Comparar los rostros. Si no coinciden, mostrar error.
    # 4. Si coinciden, proceder a registrar la entrada.

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash("Error: Debes iniciar sesión para registrar tu asistencia.", "error")
        return redirect(url_for('usuario.login'))

    try:
        asistencia_service.registrar_entrada(usuario_id)
        flash("¡Entrada registrada exitosamente!", "success")
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", "error")

    return redirect(url_for('dashboard.index'))

@asistencia_bp.route('/totem', methods=['GET'])
def totem_page():
    """Muestra la página del tótem para fichar, cerrando cualquier sesión activa."""
    session.clear()  # Cierra cualquier sesión activa para evitar conflictos.
    return render_template('usuarios/totem.html')

@asistencia_bp.route('/fichar-totem', methods=['POST'])
def fichar_totem():
    """
    Endpoint para que los usuarios fichen su entrada o salida desde el tótem.
    """
    data = request.get_json()
    if not data or 'tipo' not in data or 'imagen' not in data:
        return jsonify({'success': False, 'message': 'Datos incompletos.'}), 400

    tipo = data['tipo'].upper()
    # imagen_b64 = data['imagen'] # La imagen no se usa en la simulación

    # --- Reconocimiento Facial (Desactivado Temporalmente) ---
    # La lógica de reconocimiento facial se implementará en el futuro.
    # Por ahora, la funcionalidad está desactivada para evitar fichajes simulados.
    
    # TODO: Implementar la llamada al servicio de reconocimiento facial aquí.
    # 1. Enviar `imagen_b64` a un servicio de IA.
    # 2. Recibir el ID del usuario reconocido.
    # 3. `usuario = usuario_service.obtener_por_id(id_reconocido)`
    
    return jsonify({
        'success': False, 
        'message': 'Funcionalidad no disponible: El reconocimiento facial no está implementado.'
    }), 501 # 501 Not Implemented

@asistencia_bp.route('/registrar-salida', methods=['POST'])
def registrar_salida():
    """Registra la salida del usuario logueado."""
    # TODO: Implementar lógica de verificación facial (similar a la entrada).

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash("Error: Debes iniciar sesión para registrar tu asistencia.", "error")
        return redirect(url_for('usuario.login'))

    try:
        asistencia_service.registrar_salida(usuario_id)
        flash("¡Salida registrada exitosamente!", "success")
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", "error")

    return redirect(url_for('dashboard.index'))