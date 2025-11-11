from typing import Dict
from app.controllers.base_controller import BaseController
from app.models.control_calidad_insumo import ControlCalidadInsumoModel
from app.models.inventario import InventarioModel
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.insumo_controller import InsumoController
from app.database import Database
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
import os

try:
    from storage3.exceptions import StorageApiError
except Exception:
    # Fallback if storage3 is not installed/available in the environment.
    class StorageApiError(Exception):
        """Fallback Storage API error used when the storage3 package is unavailable."""
        pass

logger = logging.getLogger(__name__)

class ControlCalidadInsumoController(BaseController):
    """
    Controlador para la lógica de negocio del control de calidad de insumos.
    """
    def __init__(self):
        super().__init__()
        self.model = ControlCalidadInsumoModel()
        self.inventario_model = InventarioModel()
        self.orden_compra_controller = OrdenCompraController()
        self.insumo_controller = InsumoController()

    def _subir_foto_y_obtener_url(self, file_storage, lote_id: int) -> str | None:
        """
        Sube un archivo al bucket de Supabase y devuelve su URL pública.
        """
        if not file_storage or not file_storage.filename:
            return None
        try:
            db_client = Database().client
            bucket_name = "fotos_control_calidad"

            filename = secure_filename(file_storage.filename)
            extension = os.path.splitext(filename)[1]
            unique_filename = f"lote_{lote_id}_{int(datetime.now().timestamp())}{extension}"

            file_content = file_storage.read()
            
            response = db_client.storage.from_(bucket_name).upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": file_storage.mimetype}
            )
            
            url_response = db_client.storage.from_(bucket_name).get_public_url(unique_filename)
            logger.info(f"Foto subida con éxito para el lote {lote_id}. URL: {url_response}")
            return url_response

        except StorageApiError as e:
            if "Bucket not found" in str(e):
                error_message = f"Error de configuración: El bucket de almacenamiento '{bucket_name}' no se encontró en Supabase. Por favor, créelo como público o verifique los permisos de la clave API (debe ser 'service_role')."
                logger.error(error_message)
                raise Exception(error_message)
            else:
                logger.error(f"Error de Supabase Storage al subir foto para el lote {lote_id}: {e}", exc_info=True)
                raise e
        except Exception as e:
            logger.error(f"Excepción general al subir foto para el lote {lote_id}: {e}", exc_info=True)
            raise e

    def procesar_inspeccion(self, lote_id: str, decision: str, form_data: Dict, foto_file, usuario_id: int) -> tuple:
        """
        Procesa el resultado de una inspección de calidad para un lote de insumo, manejando cantidades parciales.
        """
        try:
            lote_existente_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_existente_res.get('success') or not lote_existente_res.get('data'):
                return self.error_response('El lote de insumo no fue encontrado.', 404)
            lote = lote_existente_res['data']
            insumo_id = lote.get('id_insumo')
            cantidad_original = float(lote.get('cantidad_actual', 0))

            cantidad_a_procesar_str = form_data.get('cantidad')
            cantidad_a_procesar = float(cantidad_a_procesar_str) if cantidad_a_procesar_str else cantidad_original

            # Corrección para la validación de punto flotante
            TOLERANCIA = 1e-9
            if cantidad_a_procesar <= 0 or (cantidad_a_procesar - cantidad_original) > TOLERANCIA:
                return self.error_response('La cantidad a procesar no es válida.', 400)

            es_parcial = cantidad_a_procesar < cantidad_original

            nuevo_estado_lote = {'Aceptar': 'disponible', 'Poner en Cuarentena': 'cuarentena', 'Rechazar': 'RECHAZADO'}.get(decision)
            if not nuevo_estado_lote:
                return self.error_response('La decisión tomada no es válida.', 400)

            # Lógica unificada para procesamiento parcial y total
            update_data = {}
            if decision == 'Aceptar':
                # FIX: Es necesario agregar el estado para que se ejecute el update
                update_data['estado'] = nuevo_estado_lote 
                # No se hace nada especial con la cantidad, la cantidad_actual es la disponible.
                pass
            elif decision == 'Rechazar':
                update_data['cantidad_actual'] = cantidad_original - cantidad_a_procesar
                # FIX: Es necesario agregar el estado para que se ejecute el update
                update_data['estado'] = nuevo_estado_lote
                # Opcional: registrar la cantidad rechazada en otro campo si existiera
            elif decision == 'Poner en Cuarentena':
                cantidad_en_cuarentena_actual = float(lote.get('cantidad_en_cuarentena', 0) or 0)
                update_data['cantidad_actual'] = cantidad_original - cantidad_a_procesar
                update_data['cantidad_en_cuarentena'] = cantidad_en_cuarentena_actual + cantidad_a_procesar
                update_data['estado'] = 'cuarentena'
                update_data['motivo_cuarentena'] = form_data.get('comentarios', '')

            if update_data:
                update_result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not update_result.get('success'):
                    return self.error_response(f"Error al actualizar el lote: {update_result.get('error')}", 500)
                lote_actualizado = update_result['data']
            else:
                lote_actualizado = lote

            # Registrar el evento de C.C. si es necesario
            if decision in ['Poner en Cuarentena', 'Rechazar']:
                foto_url = self._subir_foto_y_obtener_url(foto_file, lote_id)
                orden_compra_id = self._extraer_oc_id_de_lote(lote)
                
                registro_data = {
                    'lote_insumo_id': lote_id,
                    'orden_compra_id': orden_compra_id,
                    'usuario_supervisor_id': usuario_id,
                    'decision_final': decision.upper().replace(' ', '_'),
                    'comentarios': form_data.get('comentarios'),
                    'resultado_inspeccion': form_data.get('resultado_inspeccion'),
                    'foto_url': foto_url
                }
                self.model.create_registro(registro_data)

            # Recalcular el stock del insumo afectado
            if insumo_id:
                self.insumo_controller.actualizar_stock_insumo(insumo_id)

            # Verificar si la orden de compra asociada ya puede ser cerrada
            orden_compra_id_a_verificar = self._extraer_oc_id_de_lote(lote)
            if orden_compra_id_a_verificar:
                self._verificar_y_finalizar_orden_si_corresponde(orden_compra_id_a_verificar, usuario_id)
            
            return self.success_response(data=lote_actualizado, message=f"Lote {lote_id} procesado con éxito.")

        except Exception as e:
            logger.error(f"Error crítico procesando inspección para el lote {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def procesar_inspeccion_api(self, lote_id: str, decision: str, form_data: Dict, foto_file, usuario_id: int) -> tuple:
        """
        Versión API para procesar una inspección. Devuelve el lote actualizado.
        """
        try:
            resultado, status_code = self.procesar_inspeccion(lote_id, decision, form_data, foto_file, usuario_id)
            return resultado, status_code
        except Exception as e:
            logger.error(f"Error en procesar_inspeccion_api: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.'), 500

    def _extraer_oc_id_de_lote(self, lote: Dict) -> int | None:
        """
        Función de ayuda para obtener la OC ID del lote.
        ESTO ES UN PLACEHOLDER y puede necesitar una implementación más robusta.
        """
        try:
            codigo_oc = lote.get('documento_ingreso')
            if codigo_oc:
                oc_res = self.orden_compra_controller.model.find_by_codigo(codigo_oc)
                if oc_res.get('success'):
                    return oc_res['data']['id']          
        except Exception as e:
            logger.warning(f"No se pudo extraer la OC ID del lote {lote.get('id_lote')} a partir de '{lote.get('documento_ingreso')}': {e}")
        return None

    def _verificar_y_finalizar_orden_si_corresponde(self, orden_compra_id: int, usuario_id: int):
        """
        Verifica si todos los lotes de una OC han sido inspeccionados.
        Si es así, delega la finalización de la OC al OrdenCompraController.
        """
        try:
            oc_res, _ = self.orden_compra_controller.get_orden(orden_compra_id)
            if not oc_res.get('success'):
                logger.error(f"No se pudo encontrar la OC {orden_compra_id} para verificar su finalización.")
                return

            codigo_oc = oc_res['data'].get('codigo_oc')
            if not codigo_oc:
                return

            lotes_de_oc_res = self.inventario_model.find_all(
                filters={'documento_ingreso': ('ilike', f"%{codigo_oc}%")}
            )

            if not lotes_de_oc_res.get('success'):
                logger.error(f"Error al buscar lotes para la OC {codigo_oc} para finalizar.")
                return

            lotes = lotes_de_oc_res.get('data', [])
            if not lotes:
                self.orden_compra_controller.finalizar_proceso_recepcion(orden_compra_id, usuario_id)
                return

            if any(lote.get('estado') == 'EN REVISION' for lote in lotes):
                logger.info(f"La OC {orden_compra_id} no se finaliza. Aún hay lotes 'EN REVISION'.")
                return

            logger.info(f"Todos los lotes de la OC {orden_compra_id} han sido procesados. Delegando finalización.")
            self.orden_compra_controller.finalizar_proceso_recepcion(orden_compra_id, usuario_id)

        except Exception as e:
            logger.error(f"Error crítico al verificar y finalizar la OC {orden_compra_id}: {e}", exc_info=True)

    def crear_registro_control_calidad(self, lote_id: str, usuario_id: int, decision: str, comentarios: str, orden_compra_id: int = None, foto_url: str = None, resultado_inspeccion: str = None) -> tuple:
        """
        Crea un registro en la tabla de control de calidad de insumos.
        """
        try:
            registro_data = {
                'lote_insumo_id': lote_id,
                'orden_compra_id': orden_compra_id,
                'usuario_supervisor_id': usuario_id,
                'decision_final': decision.upper().replace(' ', '_'),
                'comentarios': comentarios,
                'resultado_inspeccion': resultado_inspeccion,
                'foto_url': foto_url
            }
            resultado = self.model.create_registro(registro_data)
            
            # --- INICIO: Lógica de rechazo ---
            if decision.upper() == 'RECHAZAR':
                self.manejar_rechazo_cuarentena(lote_id, usuario_id)
            # --- FIN: Lógica de rechazo ---

            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'), message="Registro de control de calidad creado con éxito.")
            else:
                return self.error_response(resultado.get('error'), 500)
        except Exception as e:
            logger.error(f"Error crítico al crear registro de control de calidad para el lote {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

    def manejar_rechazo_cuarentena(self, lote_rechazado_id: str, usuario_id: int):
        from app.controllers.orden_produccion_controller import OrdenProduccionController
        op_controller = OrdenProduccionController()
        
        try:
            # 1. Encontrar qué OPs estaban usando este lote
            reservas_afectadas = self.inventario_model.reserva_insumo_model.find_all(
                filters={'lote_inventario_id': lote_rechazado_id}
            ).get('data', [])

            for reserva in reservas_afectadas:
                op_id = reserva['orden_produccion_id']
                insumo_id = reserva['insumo_id']
                cantidad_necesaria = float(reserva['cantidad_reservada'])

                # 2. Buscar un lote de reemplazo
                lotes_disponibles = self.inventario_model._obtener_lotes_con_disponibilidad(insumo_id)
                lote_reemplazo = next((l for l in lotes_disponibles if l['disponibilidad'] >= cantidad_necesaria), None)

                if lote_reemplazo:
                    # 3. Si se encuentra reemplazo, actualizar la reserva
                    self.inventario_model.reserva_insumo_model.update(
                        reserva['id'],
                        {'lote_inventario_id': lote_reemplazo['id_lote']},
                        'id'
                    )
                    logger.info(f"Lote {lote_rechazado_id} rechazado. OP {op_id} ahora usa el lote de reemplazo {lote_reemplazo['id_lote']}.")
                else:
                    # 4. Si no hay reemplazo, poner la OP en PENDIENTE
                    op_controller.model.update(op_id, {'estado': 'PENDIENTE'}, 'id')
                    logger.warning(f"Lote {lote_rechazado_id} rechazado. No se encontró reemplazo para la OP {op_id}, que ha sido puesta en 'PENDIENTE'.")
                    
                    # También se debe eliminar la reserva original para no dejar inconsistencias
                    self.inventario_model.reserva_insumo_model.delete(reserva['id'], 'id')

        except Exception as e:
            logger.error(f"Error al manejar el rechazo del lote {lote_rechazado_id}: {e}", exc_info=True)