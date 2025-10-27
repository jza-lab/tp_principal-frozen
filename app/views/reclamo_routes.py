from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from app.controllers.reclamo_controller import ReclamoController
# Faltaba FlaskForm
from flask_wtf import FlaskForm


reclamo_bp = Blueprint('reclamo', __name__, url_prefix='/api/reclamos')
controller = ReclamoController()

@reclamo_bp.route('/', methods=['POST'])
def crear_reclamo():
    """
    Endpoint para crear un nuevo reclamo.
    Espera un JSON con los datos del reclamo.
    """
    datos_json = request.get_json()
    if not datos_json:
        return jsonify({"success": False, "error": "No se recibieron datos JSON."}), 400
    
    # El ID del cliente se obtiene de la sesión para seguridad
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        return jsonify({"success": False, "error": "Sesión no válida."}), 401
    
    respuesta, status_code = controller.crear_reclamo(datos_json, cliente_id)
    
    return jsonify(respuesta), status_code

@reclamo_bp.route('/', methods=['GET'])
def obtener_reclamos():
    """
    Endpoint para obtener todos los reclamos del cliente que ha iniciado sesión.
    """
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        return jsonify({"success": False, "error": "Sesión no válida."}), 401
        
    respuesta, status_code = controller.obtener_reclamos_por_cliente(cliente_id)
    
    return jsonify(respuesta), status_code

# --- NUEVAS RUTAS PÚBLICAS ---

@reclamo_bp.route('/<int:reclamo_id>', methods=['GET'])
def obtener_detalle_reclamo(reclamo_id):
    """
    Muestra la página de detalle (chat) de un reclamo para el cliente.
    """
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        flash('Por favor, inicia sesión para ver tus reclamos.', 'info')
        return redirect(url_for('cliente.login'))
        
    respuesta, status_code = controller.obtener_detalle_reclamo(reclamo_id)
    
    if not respuesta.get('success'):
        flash(respuesta.get('error', 'Reclamo no encontrado.'), 'error')
        return redirect(url_for('cliente.perfil'))
        
    reclamo = respuesta.get('data')
    
    # Verificación de seguridad
    if reclamo.get('cliente_id') != cliente_id:
        flash('No tienes permiso para ver este reclamo.', 'error')
        return redirect(url_for('cliente.perfil'))
        
    return render_template('public/reclamo_detalle.html', reclamo=reclamo, csrf_form=FlaskForm())

@reclamo_bp.route('/<int:reclamo_id>/responder', methods=['POST'])
def responder_reclamo_cliente(reclamo_id):
    """
    Endpoint para que el cliente envíe una respuesta a un reclamo.
    """
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        flash('Sesión expirada.', 'error')
        return redirect(url_for('cliente.login'))
        
    mensaje = request.form.get('mensaje')
    if not mensaje:
        flash('La respuesta no puede estar vacía.', 'error')
        return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))

    # Verificar que el reclamo pertenece al cliente
    reclamo_resp, _ = controller.obtener_detalle_reclamo(reclamo_id)
    if not reclamo_resp.get('success') or reclamo_resp['data'].get('cliente_id') != cliente_id:
        flash('No tienes permiso para responder a este reclamo.', 'error')
        return redirect(url_for('cliente.perfil'))

    respuesta, status_code = controller.responder_reclamo_cliente(reclamo_id, cliente_id, mensaje)
    
    if status_code == 201:
        flash('Respuesta enviada. El administrador la revisará a la brevedad.', 'success')
    else:
        flash(f"Error: {respuesta.get('error', 'No se pudo enviar la respuesta.')}", 'error')
        
    return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))

@reclamo_bp.route('/<int:reclamo_id>/resolver', methods=['POST'])
def resolver_reclamo_cliente(reclamo_id):
    """
    Endpoint para que el cliente marque un reclamo como solucionado.
    """
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        flash('Sesión expirada.', 'error')
        return redirect(url_for('cliente.login'))

    # Verificar que el reclamo pertenece al cliente
    reclamo_resp, _ = controller.obtener_detalle_reclamo(reclamo_id)
    if not reclamo_resp.get('success') or reclamo_resp['data'].get('cliente_id') != cliente_id:
        flash('No tienes permiso para esta acción.', 'error')
        return redirect(url_for('cliente.perfil'))

    respuesta, status_code = controller.cerrar_reclamo_cliente(reclamo_id)
    
    if status_code == 200:
        flash('¡Qué bueno! Marcaste este reclamo como solucionado.', 'success')
    else:
        flash(f"Error: {respuesta.get('error', 'No se pudo actualizar el estado.')}", 'error')
        
    return redirect(url_for('reclamo.obtener_detalle_reclamo', reclamo_id=reclamo_id))