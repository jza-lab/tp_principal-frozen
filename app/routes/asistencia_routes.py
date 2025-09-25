from flask import Blueprint, redirect, url_for, flash, session
from app.services.asistencia_service import AsistenciaService
from app.repositories.asistencia_repository import AsistenciaRepository

asistencia_bp = Blueprint('asistencia', __name__, url_prefix='/asistencia')

# Inyección de dependencias
asistencia_repo = AsistenciaRepository()
asistencia_service = AsistenciaService(asistencia_repo)

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