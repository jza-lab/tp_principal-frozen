from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.reclamo_controller import ReclamoController
from app.utils.decorators import permission_required

admin_reclamo_bp = Blueprint('admin_reclamo', __name__, url_prefix='/admin/reclamos')

@admin_reclamo_bp.route('/')
@jwt_required()
@permission_required(accion='gestionar_reclamos') # Permiso nuevo
def listar_reclamos():
    """
    Muestra el panel de administración con todos los reclamos.
    """
    controller = ReclamoController()
    response, _ = controller.obtener_reclamos_admin()
    reclamos = response.get('data', [])
    
    # Filtrar por estado (opcional, desde query param)
    estado_filtro = request.args.get('estado')
    if estado_filtro:
        reclamos = [r for r in reclamos if r.get('estado') == estado_filtro]
        
    return render_template('admin_reclamos/listar.html', reclamos=reclamos)

@admin_reclamo_bp.route('/<int:reclamo_id>')
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def detalle_reclamo(reclamo_id):
    """
    Muestra la vista de "chat" para que un admin responda un reclamo.
    """
    controller = ReclamoController()
    response, _ = controller.obtener_detalle_reclamo(reclamo_id)
    if not response.get('success'):
        flash(response.get('error', 'Reclamo no encontrado.'), 'error')
        return redirect(url_for('admin_reclamo.listar_reclamos'))
        
    reclamo = response.get('data')
    return render_template('admin_reclamos/detalle.html', reclamo=reclamo)

@admin_reclamo_bp.route('/<int:reclamo_id>/responder', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def responder_reclamo(reclamo_id):
    """
    Endpoint API para que el admin envíe una respuesta.
    """
    admin_usuario_id = get_jwt_identity()
    data = request.form
    mensaje = data.get('mensaje')

    if not mensaje:
        flash('La respuesta no puede estar vacía.', 'error')
        return redirect(url_for('admin_reclamo.detalle_reclamo', reclamo_id=reclamo_id))

    controller = ReclamoController()
    response, status_code = controller.responder_reclamo_admin(reclamo_id, admin_usuario_id, mensaje)
    
    if status_code == 201:
        flash('Respuesta enviada con éxito.', 'success')
    else:
        flash(f"Error: {response.get('error', 'No se pudo enviar la respuesta.')}", 'error')
        
    return redirect(url_for('admin_reclamo.detalle_reclamo', reclamo_id=reclamo_id))

@admin_reclamo_bp.route('/<int:reclamo_id>/cancelar', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def cancelar_reclamo(reclamo_id):
    """
    Endpoint para que el admin cancele un reclamo.
    """
    controller = ReclamoController()
    response, status_code = controller.cancelar_reclamo_admin(reclamo_id)
    
    if status_code == 200:
        flash('Reclamo cancelado.', 'success')
    else:
        flash(f"Error: {response.get('error', 'No se pudo cancelar.')}", 'error')
        
    return redirect(url_for('admin_reclamo.detalle_reclamo', reclamo_id=reclamo_id))