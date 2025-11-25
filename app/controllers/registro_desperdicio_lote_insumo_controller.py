# app/controllers/registro_desperdicio_lote_insumo_controller.py
from app.controllers.base_controller import BaseController
from app.models.inventario import InventarioModel
from app.models.registro_desperdicio_lote_insumo_model import RegistroDesperdicioLoteInsumoModel
from app.controllers.storage_controller import StorageController
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RegistroDesperdicioLoteInsumoController(BaseController):
    def __init__(self):
        super().__init__()
        self.inventario_model = InventarioModel()
        self.registro_desperdicio_model = RegistroDesperdicioLoteInsumoModel()

    def registrar_desperdicio(self, lote_insumo_id: str, form_data: dict, usuario_id: int, file) -> tuple:
        """Registra un desperdicio para un lote de insumo."""
        try:
            lote_res = self.inventario_model.find_by_id(lote_insumo_id, 'id_lote')
            if not lote_res.get('success') or not lote_res.get('data'):
                return self.error_response('Lote no encontrado', 404)

            lote = lote_res['data']
            cantidad_a_desperdiciar = float(form_data.get('cantidad'))
            
            stock_disponible = float(lote.get('cantidad_actual', 0.0))
            stock_cuarentena = float(lote.get('cantidad_en_cuarentena', 0.0))
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
                bucket_name = "registro_desperdicio_lote_insumo"
                filename = secure_filename(file.filename)
                destination_path = f"{lote_insumo_id}/{int(time.time())}_{filename}"

                upload_result, status_code = storage_controller.upload_file(file, bucket_name, destination_path)

                if status_code == 200 and upload_result.get('success'):
                    foto_url = upload_result.get('url')
                else:
                    error_msg = upload_result.get('error', 'Error desconocido al subir la foto.')
                    return self.error_response(f"Error al subir la foto: {error_msg}", 500)

            motivo_id = form_data.get('motivo_id')
            if not motivo_id:
                return self.error_response("El campo 'Motivo' es obligatorio.", 400)

            data_registro = {
                'lote_insumo_id': lote_insumo_id,
                'motivo_id': int(motivo_id),
                'cantidad': cantidad_a_desperdiciar,
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
            }

            # Si se agota todo el stock, marcar como RETIRADO
            if nueva_cantidad_disponible <= 0 and nueva_cantidad_cuarentena <= 0:
                update_data['estado'] = 'RETIRADO'

            self.inventario_model.update(lote_insumo_id, update_data, 'id_lote')

            # --- 5. Gestionar OPs Afectadas ---
            accion_ops = form_data.get('accion_ops', 'ignorar')
            if accion_ops != 'ignorar':
                from app.models.reserva_insumo import ReservaInsumoModel
                from app.controllers.orden_produccion_controller import OrdenProduccionController
                from app.controllers.inventario_controller import InventarioController
                
                reserva_model = ReservaInsumoModel()
                op_controller = OrdenProduccionController()
                inventario_controller = InventarioController()
                
                reservas_afectadas = reserva_model.find_all(filters={'lote_inventario_id': lote_insumo_id}).get('data', [])
                op_ids_afectadas = set(r['orden_produccion_id'] for r in reservas_afectadas)
                
                ops_procesadas = 0
                for op_id in op_ids_afectadas:
                    op_res = op_controller.obtener_orden_por_id(op_id)
                    if not op_res.get('success'): continue
                    op_data = op_res['data']
                    
                    # Solo actuar sobre OPs activas
                    if op_data.get('estado') in ['COMPLETADA', 'FINALIZADA', 'CANCELADA']:
                        continue

                    if accion_ops == 'replanificar':
                        inventario_controller.liberar_stock_reservado_para_op(op_id)
                        op_controller.cambiar_estado_orden_simple(op_id, 'PENDIENTE')
                        logger.info(f"OP {op_id} reseteada a PENDIENTE por retiro de insumo {lote_insumo_id}.")
                        ops_procesadas += 1
                    
                    elif accion_ops == 'cancelar':
                        op_controller.rechazar_orden(op_id, f"Cancelada por retiro de insumo Lote {lote.get('numero_lote_proveedor')}")
                        logger.info(f"OP {op_id} CANCELADA por retiro de insumo {lote_insumo_id}.")
                        ops_procesadas += 1

            return self.success_response(message="Desperdicio registrado con éxito.")
        except Exception as e:
            logger.error(f"Error en registrar_desperdicio: {e}", exc_info=True)
            return self.error_response('Error interno del servidor', 500)

    def allowed_file(self, filename: str) -> bool:
        """Verifica si la extensión del archivo está permitida."""
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
