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
        Procesa el resultado de una inspección de calidad para un lote de insumo.
        """
        try:
            lote_existente_res = self.inventario_model.find_by_id(lote_id, 'id_lote')
            if not lote_existente_res.get('success') or not lote_existente_res.get('data'):
                return self.error_response('El lote de insumo no fue encontrado.', 404)
            lote = lote_existente_res['data']

            nuevo_estado_lote = {
                'Aceptar': 'disponible',
                'Poner en Cuarentena': 'en cuarentena',
                'Rechazar': 'rechazado'
            }.get(decision)

            if not nuevo_estado_lote:
                return self.error_response('La decisión tomada no es válida.', 400)

            update_data = {'estado': nuevo_estado_lote, 'updated_at': datetime.now().isoformat()}
            update_result = self.inventario_model.update(lote_id, update_data, 'id_lote')

            if not update_result.get('success'):
                return self.error_response(f"Error al actualizar el estado del lote: {update_result.get('error')}", 500)

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
                    logger.error(f"El estado del lote {lote_id} se actualizó, pero falló la creación del registro de C.C.: {registro_result.get('error')}")

            orden_compra_id_a_verificar = self._extraer_oc_id_de_lote(lote)
            if orden_compra_id_a_verificar:
                self._verificar_y_cerrar_orden_si_completa(orden_compra_id_a_verificar)
            
            return self.success_response(message=f"Lote {lote_id} procesado con éxito. Nuevo estado: {nuevo_estado_lote}.")

        except Exception as e:
            logger.error(f"Error crítico procesando inspección para el lote {lote_id}: {e}", exc_info=True)
            return self.error_response('Error interno del servidor.', 500)

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
            lotes_de_oc_res = self.inventario_model.find_all(filters={'documento_ingreso': f"OC-{codigo_oc}"})

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

