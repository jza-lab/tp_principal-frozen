from flask import Blueprint, redirect, url_for, flash, session
from controllers.asistencia_controller import AsistenciaController

asistencia_bp = Blueprint('asistencia', __name__, url_prefix='/asistencia')
controller = AsistenciaController()

@asistencia_bp.route('/registrar-entrada', methods=['POST'])
def registrar_entrada():
    """
    Endpoint para registrar el fichaje de entrada de un usuario.
    Llama al controlador de asistencia para manejar la lógica de negocio.
    """
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash("Error: Debes iniciar sesión para registrar tu asistencia.", "error")
        return redirect(url_for('usuario.login'))

    # TODO: Implementar lógica de verificación facial aquí.

    resultado = controller.registrar_entrada(usuario_id)

    if resultado.get('success'):
        flash("¡Entrada registrada exitosamente!", "success")
    else:
        flash(resultado.get('error', 'Ocurrió un error inesperado.'), 'error')

    return redirect(url_for('dashboard.index'))

@asistencia_bp.route('/registrar-salida', methods=['POST'])
def registrar_salida():
    """
    Endpoint para registrar el fichaje de salida de un usuario.
    Llama al controlador de asistencia para manejar la lógica de negocio.
    """
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash("Error: Debes iniciar sesión para registrar tu asistencia.", "error")
        return redirect(url_for('usuario.login'))

    # TODO: Implementar lógica de verificación facial aquí.

    resultado = controller.registrar_salida(usuario_id)

    if resultado.get('success'):
        flash("¡Salida registrada exitosamente!", "success")
    else:
        flash(resultado.get('error', 'Ocurrió un error inesperado.'), 'error')

    return redirect(url_for('dashboard.index'))