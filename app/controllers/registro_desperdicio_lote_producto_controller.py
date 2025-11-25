# app/controllers/registro_desperdicio_lote_producto_controller.py
from app.controllers.base_controller import BaseController
from app.models.lote_producto import LoteProductoModel
from app.models.motivo_desperdicio_lote_model import MotivoDesperdicioLoteModel
from app.models.registro_desperdicio_lote_producto_model import RegistroDesperdicioLoteProductoModel
from app.controllers.storage_controller import StorageController
import logging

logger = logging.getLogger(__name__)

class RegistroDesperdicioLoteProductoController(BaseController):
    def __init__(self):
        super().__init__()
        self.lote_producto_model = LoteProductoModel()
        self.motivo_desperdicio_lote_model = MotivoDesperdicioLoteModel()
        self.registro_desperdicio_model = RegistroDesperdicioLoteProductoModel()

    def registrar_desperdicio(self, lote_id: int, form_data: dict, usuario_id: int, file) -> tuple:
        """Registra un desperdicio para un lote de producto."""
        try:
            lote_res = self.lote_producto_model.find_by_id(lote_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_a_desperdiciar = float(form_data.get('cantidad'))
            
            stock_disponible = lote.get('cantidad_actual', 0)
            stock_cuarentena = lote.get('cantidad_en_cuarentena', 0)
            stock_total = stock_disponible + stock_cuarentena

            if cantidad_a_desperdiciar <= 0:
                return self.error_response("La cantidad a desperdiciar debe ser un número positivo.", 400)

            if cantidad_a_desperdiciar > stock_total:
                return self.error_response(f"La cantidad a desperdiciar ({cantidad_a_desperdiciar}) excede el stock total ({stock_total}).", 400)

            foto_url = None
            if file and file.filename:
                if not self.allowed_file(file.filename):
                    return self.error_response("Tipo de archivo no permitido. Solo se aceptan imágenes (png, jpg, jpeg, gif).", 400)

                from werkzeug.utils import secure_filename
                import time

                storage_controller = StorageController()
                bucket_name = "registro_desperdicio_lote_producto"
                filename = secure_filename(file.filename)
                destination_path = f"{lote_id}/{int(time.time())}_{filename}"

                upload_result, status_code = storage_controller.upload_file(file, bucket_name, destination_path)

                if status_code == 200 and upload_result.get('success'):
                    foto_url = upload_result.get('url')
                else:
                    error_msg = upload_result.get('error', 'Error desconocido al subir la foto.')
                    return self.error_response(f"Error al subir la foto: {error_msg}", 500)

            motivo_id = form_data.get('motivo_id')
            if not motivo_id:
                return self.error_response("El campo 'Motivo' es obligatorio.", 400)

            detalle = form_data.get('detalle')
            if not detalle:
                return self.error_response("El campo 'Detalle' es obligatorio.", 400)

            data_registro = {
                'lote_producto_id': lote_id,
                'motivo_id': int(motivo_id),
                'cantidad': cantidad_a_desperdiciar,
                'detalle': detalle,
                'comentarios': form_data.get('comentarios'),
                'foto_url': foto_url,
                'usuario_id': usuario_id
            }
            create_res = self.registro_desperdicio_model.create(data_registro)
            if not create_res.get('success'):
                error_msg = f"No se pudo guardar el registro de desperdicio: {create_res.get('error')}"
                logger.error(error_msg)
                return self.error_response(error_msg, 500)

            # Lógica de descuento de stock mejorada
            nueva_cantidad_cuarentena = stock_cuarentena
            nueva_cantidad_disponible = stock_disponible
            remanente_a_descontar = cantidad_a_desperdiciar

            # Prioridad: descontar de cuarentena primero
            if stock_cuarentena > 0:
                descuento_cuarentena = min(stock_cuarentena, remanente_a_descontar)
                nueva_cantidad_cuarentena -= descuento_cuarentena
                remanente_a_descontar -= descuento_cuarentena
            
            if remanente_a_descontar > 0:
                nueva_cantidad_disponible -= remanente_a_descontar

            # Preparar datos para actualizar el lote
            update_data = {
                'cantidad_actual': nueva_cantidad_disponible,
                'cantidad_en_cuarentena': nueva_cantidad_cuarentena,
                'cantidad_desperdiciada': lote.get('cantidad_desperdiciada', 0) + cantidad_a_desperdiciar
            }

            # Si se agota todo el stock, marcar como RETIRADO
            if nueva_cantidad_disponible <= 0 and nueva_cantidad_cuarentena <= 0:
                update_data['estado'] = 'RETIRADO'

            self.lote_producto_model.update(lote_id, update_data, 'id_lote')

            return self.success_response(message="Desperdicio registrado con éxito.")
        except Exception as e:
            logger.error(f"Error en registrar_desperdicio: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def allowed_file(self, filename: str) -> bool:
        """Verifica si la extensión del archivo está permitida."""
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
