from flask import Blueprint, request, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.inventario_controller import InventarioController
from app.controllers.base_controller import BaseController

registro_desperdicio_lote_insumo_bp = Blueprint('registro_desperdicio_lote_insumo', __name__, url_prefix='/inventario/lote')

class RegistroDesperdicioLoteInsumoController(BaseController):
    def __init__(self):
        super().__init__()
        self.inventario_controller = InventarioController()

    def registrar_desperdicio(self, lote_insumo_id):
        try:
            usuario_id = get_jwt_identity()
            form_data = request.form
            foto_file = request.files.get('foto')

            cantidad = float(form_data.get('cantidad'))
            motivo_id = int(form_data.get('motivo_id'))
            comentarios = form_data.get('comentarios', '')
            accion_ops = form_data.get('accion_ops', 'replanificar')

            response, status_code = self.inventario_controller.retirar_lote_insumo_unificado(
                lote_id=lote_insumo_id,
                cantidad=cantidad,
                motivo_id=motivo_id,
                comentarios=comentarios,
                usuario_id=usuario_id,
                foto_file=foto_file,
                usar_foto_cuarentena=False,
                accion_ops=accion_ops
            )

            if response.get('success'):
                flash(response.get('message', 'Desperdicio registrado con éxito.'), 'success')
            else:
                flash(response.get('error', 'Ocurrió un error al registrar el desperdicio.'), 'danger')

        except (ValueError, TypeError) as e:
            flash(f'Error en los datos enviados: {e}', 'danger')
        except Exception as e:
            flash(f'Ocurrió un error inesperado: {e}', 'danger')

        return redirect(url_for('inventario_view.detalle_lote', id_lote=lote_insumo_id))

@registro_desperdicio_lote_insumo_bp.route('/<string:lote_insumo_id>/registrar-desperdicio', methods=['POST'])
@jwt_required()
def registrar_desperdicio(lote_insumo_id):
    controller = RegistroDesperdicioLoteInsumoController()
    return controller.registrar_desperdicio(lote_insumo_id)
