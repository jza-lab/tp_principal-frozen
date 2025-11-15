# app/views/registro_desperdicio_lote_producto_routes.py
from flask import Blueprint, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.registro_desperdicio_lote_producto_controller import RegistroDesperdicioLoteProductoController

registro_desperdicio_lote_producto_bp = Blueprint('registro_desperdicio_lote_producto', __name__, url_prefix='/lotes-productos')

@registro_desperdicio_lote_producto_bp.route('/<int:lote_id>/registrar-desperdicio', methods=['POST'])
@jwt_required()
def registrar_desperdicio(lote_id):
    """Registra un desperdicio para un lote de producto."""
    controller = RegistroDesperdicioLoteProductoController()
    usuario_id = get_jwt_identity()
    foto = request.files.get('foto')
    
    response, status_code = controller.registrar_desperdicio(lote_id, request.form, usuario_id, foto)

    if response.get('success'):
        flash(response.get('message'), 'success')
    else:
        flash(response.get('error'), 'danger')

    return redirect(url_for('lote_producto.detalle_lote', id_lote=lote_id))
