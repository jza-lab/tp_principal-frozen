from typing import Dict
from app.controllers.base_controller import BaseController
from app.models.control_calidad_insumo import ControlCalidadInsumoModel
from app.models.inventario import InventarioModel
from app.controllers.orden_compra_controller import OrdenCompraController
from app.database import Database
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
import os

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

            if response.status_code != 200:
                error_details = response.json()
                logger.error(f"Error al subir foto a Supabase Storage: {error_details.get('message', 'Error desconocido')}")
                return None
            
            url_response = db_client.storage.from_(bucket_name).get_public_url(unique_filename)
            logger.info(f"Foto subida con éxito para el lote {lote_id}. URL: {url_response}")
            return url_response

        except Exception as e:
            logger.error(f"Excepción al subir foto para el lote {lote_id}: {e}", exc_info=True)
            return None

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

            if cantidad_a_procesar <= 0 or cantidad_a_procesar > cantidad_original:
                return self.error_response('La cantidad a procesar no es válida.', 400)

            es_parcial = cantidad_a_procesar < cantidad_original

            nuevo_estado_lote = {'Aceptar': 'disponible', 'Poner en Cuarentena': 'cuarentena', 'Rechazar': 'RECHAZADO'}.get(decision)
            if not nuevo_estado_lote:
                return self.error_response('La decisión tomada no es válida.', 400)

            if not es_parcial:
                # Lógica original para el lote completo
                update_data = {'estado': nuevo_estado_lote}
                if decision == 'Rechazar':
                    update_data['cantidad_actual'] = 0
                elif decision == 'Poner en Cuarentena':
                    update_data['cantidad_actual'] = 0
                    update_data['cantidad_en_cuarentena'] = cantidad_original
                    update_data['motivo_cuarentena'] = form_data.get('comentarios', '')
                
                update_result = self.inventario_model.update(lote_id, update_data, 'id_lote')
                if not update_result.get('success'):
                    return self.error_response(f"Error al actualizar el lote completo: {update_result.get('error')}", 500)
                lote_actualizado = update_result['data']
            else:
                # Lógica para división de lote
                # 1. Actualizar lote original
                update_data_original = {'cantidad_actual': cantidad_original - cantidad_a_procesar}
                update_result_original = self.inventario_model.update(lote_id, update_data_original, 'id_lote')
                if not update_result_original.get('success'):
                    return self.error_response(f"Error al actualizar el lote original: {update_result_original.get('error')}", 500)
                
                # 2. Crear nuevo lote para la parte procesada
                nuevo_lote_data = lote.copy()
                del nuevo_lote_data['id_lote']
                del nuevo_lote_data['created_at']
                nuevo_lote_data['cantidad_inicial'] = cantidad_a_procesar
                nuevo_lote_data['cantidad_actual'] = 0 if decision in ['Rechazar', 'Poner en Cuarentena'] else cantidad_a_procesar
                nuevo_lote_data['cantidad_en_cuarentena'] = cantidad_a_procesar if decision == 'Poner en Cuarentena' else 0
                nuevo_lote_data['estado'] = nuevo_estado_lote
                nuevo_lote_data['motivo_cuarentena'] = form_data.get('comentarios', '') if decision == 'Poner en Cuarentena' else None
                nuevo_lote_data['numero_lote_proveedor'] = f"{lote.get('numero_lote_proveedor', 'LOTE')}-PARCIAL"

                create_result = self.inventario_model.create(nuevo_lote_data)
                if not create_result.get('success'):
                     # Intentar revertir la actualización del lote original
                    self.inventario_model.update(lote_id, {'cantidad_actual': cantidad_original}, 'id_lote')
                    return self.error_response(f"Error al crear el nuevo lote parcial: {create_result.get('error')}", 500)
                lote_actualizado = create_result['data']

            # Registrar el evento de C.C. si es necesario
            if decision in ['Poner en Cuarentena', 'Rechazar']:
                foto_url = self._subir_foto_y_obtener_url(foto_file, lote_actualizado.get('id_lote'))
                orden_compra_id = self._extraer_oc_id_de_lote(lote)
                
                registro_data = {
                    'lote_insumo_id': lote_actualizado.get('id_lote'),
                    'orden_compra_id': orden_compra_id,
                    'usuario_supervisor_id': usuario_id,
                    'decision_final': decision.upper().replace(' ', '_'),
                    'comentarios': form_data.get('comentarios'),
                    'foto_url': foto_url
                }
                self.model.create_registro(registro_data)

            # Recalcular el stock del insumo afectado
            if insumo_id:
                self.inventario_model.recalcular_stock_para_insumo(insumo_id)

            # Verificar si la orden de compra asociada ya puede ser cerrada
            orden_compra_id_a_verificar = self._extraer_oc_id_de_lote(lote)
            if orden_compra_id_a_verificar:
                self._verificar_y_cerrar_orden_si_completa(orden_compra_id_a_verificar)
            
            return self.success_response(data=lote_actualizado, message=f"Lote {lote_id} procesado con éxito.")
        except Exception as e:
            logger.error(f"Error crítico procesando inspección para el lote {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

            # Registrar el evento de C.C. si es necesario
            if decision in ['Poner en Cuarentena', 'Rechazar']:
                foto_url = self._subir_foto_y_obtener_url(foto_file, lote_id)
                orden_compra_id = self._extraer_oc_id_de_lote(lote)
                
                registro_data = {
                    'lote_insumo_id': lote_id,
                    'orden_compra_id': orden_compra_id,
                    'usuario_supervisor_id': usuario_id,
                    'decision_final': decision.upper().replace(' ', '_'),
                    'resultado_inspeccion': form_data.get('resultado_inspeccion'),
                    'comentarios': form_data.get('comentarios'),
                    'foto_url': foto_url
                }
                registro_result = self.model.create_registro(registro_data)
                if not registro_result.get('success'):
                    logger.error(f"Falló la creación del registro de C.C. para el lote {lote_id}: {registro_result.get('error')}")

            # Recalcular el stock del insumo afectado
            if insumo_id:
                recalculo_res = self.inventario_model.recalcular_stock_para_insumo(insumo_id)
                if not recalculo_res.get('success'):
                    logger.error(f"El lote {lote_id} se actualizó, pero falló el recálculo de stock para el insumo {insumo_id}: {recalculo_res.get('error')}")

            # Verificar si la orden de compra asociada ya puede ser cerrada
            orden_compra_id_a_verificar = self._extraer_oc_id_de_lote(lote)
            if orden_compra_id_a_verificar:
                self._verificar_y_cerrar_orden_si_completa(orden_compra_id_a_verificar)
            
            return self.success_response(data=update_result.get('data'), message=f"Lote {lote_id} procesado con éxito. Nuevo estado: {nuevo_estado_lote}.")

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

    def finalizar_inspeccion_orden(self, orden_compra_id: int) -> tuple:
        """
        Cierra una orden de compra una vez que toda la inspección ha terminado.
        """
        try:
            self._verificar_y_cerrar_orden_si_completa(orden_compra_id)
            return self.success_response(message=f"Proceso de finalización para la orden {orden_compra_id} ejecutado.")
        except Exception as e:
            logger.error(f"Error al finalizar la inspección para la orden {orden_compra_id}: {e}", exc_info=True)
            return self.error_response("Error interno al intentar finalizar la inspección."), 500

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

    def _verificar_y_cerrar_orden_si_completa(self, orden_compra_id: int):
        """
        Verifica si todos los lotes de una OC ya han sido inspeccionados (no están 'EN REVISION')
        y, si es así, cierra la orden.
        """
        try:
            # 1. Obtener el código de la OC para buscar los lotes asociados
            oc_res, _ = self.orden_compra_controller.get_orden(orden_compra_id)
            if not oc_res.get('success'):
                logger.error(f"No se pudo encontrar la OC {orden_compra_id} para verificar su cierre.")
                return
            
            codigo_oc = oc_res['data'].get('codigo_oc')
            if not codigo_oc:
                logger.error(f"La OC {orden_compra_id} no tiene un código para buscar sus lotes.")
                return

            # 2. Buscar todos los lotes asociados a esa OC por el documento de ingreso
            documento_ingreso = codigo_oc if codigo_oc.startswith('OC-') else f"OC-{codigo_oc}"
            lotes_de_oc_res = self.inventario_model.get_all_lotes_for_view(filtros={'documento_ingreso': documento_ingreso})

            if not lotes_de_oc_res.get('success'):
                logger.error(f"No se pudieron obtener los lotes para la OC {codigo_oc}.")
                return

            lotes = lotes_de_oc_res.get('data', [])
            if not lotes:
                logger.warning(f"No se encontraron lotes para la OC {codigo_oc}, procediendo a cerrar.")
                self.orden_compra_controller.marcar_como_cerrada(orden_compra_id)
                return

            # 3. Verificar si algún lote todavía está pendiente de revisión
            for lote in lotes:
                if lote.get('estado') == 'EN REVISION':
                    logger.info(f"La OC {orden_compra_id} no se cierra. El lote {lote.get('id_lote')} aún está 'EN REVISION'.")
                    return # Si al menos uno está en revisión, no hacemos nada y salimos.

            # 4. Si el bucle termina, significa que ningún lote está 'EN REVISION'. Cerramos la OC.
            logger.info(f"Todos los lotes de la OC {orden_compra_id} han sido procesados. Cerrando la orden.")
            self.orden_compra_controller.marcar_como_cerrada(orden_compra_id)

        except Exception as e:
            logger.error(f"Error crítico al verificar y cerrar la OC {orden_compra_id}: {e}", exc_info=True)

