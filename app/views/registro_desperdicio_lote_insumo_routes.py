from flask import Blueprint, request, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.registro_desperdicio_lote_insumo_controller import RegistroDesperdicioLoteInsumoController

registro_desperdicio_lote_insumo_bp = Blueprint('registro_desperdicio_lote_insumo', __name__, url_prefix='/inventario/lote')

@registro_desperdicio_lote_insumo_bp.route('/<string:lote_insumo_id>/registrar-desperdicio', methods=['POST'])
@jwt_required()
def registrar_desperdicio(lote_insumo_id):
    controller = RegistroDesperdicioLoteInsumoController()
    usuario_id = get_jwt_identity()
    foto = request.files.get('foto')
    
    response, status_code = controller.registrar_desperdicio(lote_insumo_id, request.form, usuario_id, foto)

    if response.get('success'):
        flash(response.get('message'), 'success')
        return redirect(url_for('inventario_view.detalle_lote', id_lote=lote_insumo_id))
    else:
        flash(response.get('error'), 'danger')
        return redirect(url_for('inventario_view.detalle_lote', id_lote=lote_insumo_id))
