from app.models.reclamo_proveedor_model import ReclamoProveedorModel
from app.models.orden_compra_model import OrdenCompraModel
from app.models.reclamo_proveedor_item_model import ReclamoProveedorItemModel
from app.schemas.reclamo_proveedor_schema import ReclamoProveedorSchema
from app.schemas.reclamo_proveedor_item_schema import ReclamoProveedorItemSchema
from marshmallow import ValidationError
from app.controllers.base_controller import BaseController
from app.services.email_service import send_email
from flask import current_app
from app.controllers.proveedor_controller import ProveedorController
import logging

logger = logging.getLogger(__name__)

class ReclamoProveedorController(BaseController):
    def __init__(self):
        self.model = ReclamoProveedorModel()
        self.item_model = ReclamoProveedorItemModel()
        self.schema = ReclamoProveedorSchema()
        self.item_schema = ReclamoProveedorItemSchema()
        self.proveedor_controller = ProveedorController()
        self.orden_compra_model = OrdenCompraModel()

    def _parse_reclamo_form_data(self, form_data):
        reclamo_data = {
            'orden_compra_id': form_data.get('orden_compra_id'),
            'proveedor_id': form_data.get('proveedor_id'),
            'motivo': form_data.get('motivo'),
            'descripcion_problema': form_data.get('descripcion_problema')
        }

        items_data = []
        insumo_ids = form_data.getlist('insumo_id[]')
        cantidades = form_data.getlist('cantidad_reclamada[]')
        motivos = form_data.getlist('motivo_item[]')

        for i in range(len(insumo_ids)):
            if insumo_ids[i] and float(cantidades[i] or 0) > 0:
                items_data.append({
                    'insumo_id': insumo_ids[i],
                    'cantidad_reclamada': float(cantidades[i]),
                    'motivo': motivos[i] if i < len(motivos) else None
                })
        
        return reclamo_data, items_data

    def crear_reclamo_con_items(self, form_data):
        try:
            reclamo_data, items_data = self._parse_reclamo_form_data(form_data)

            validated_data = self.schema.load(reclamo_data)
            validated_data['estado'] = 'ABIERTO'

            response = self.model.create(validated_data)

            if not response.get('success'):
                return self.error_response(response.get('error', 'Error al crear el reclamo.'), 500)

            reclamo_creado = response.get('data')
            reclamo_id = reclamo_creado.get('id')

            for item_data in items_data:
                item_data['reclamo_id'] = reclamo_id
                validated_item_data = self.item_schema.load(item_data)
                self.item_model.create(validated_item_data)
            
            # (Opcional) Enviar email...
            # ...

            return self.success_response(reclamo_creado, "Reclamo creado exitosamente con sus ítems.")

        except ValidationError as e:
            logger.error(f"Error de validación al crear reclamo: {e.messages}")
            return self.error_response(e.messages, 400)
        except Exception as e:
            logger.error(f"Error inesperado al crear reclamo: {e}", exc_info=True)
            return self.error_response(f"Error inesperado: {str(e)}", 500)

    def get_all_reclamos(self):
        try:
            enriched_query = "*, proveedor:proveedores(nombre), orden:ordenes_compra(codigo_oc)"
            response = self.model.find_all(select_query=enriched_query, order_by='created_at.desc')
            
            if response.get('success'):
                return self.success_response(response['data'])
            
            return self.success_response([], "No se encontraron reclamos.")
        except Exception as e:
            logger.error(f"Error al obtener reclamos: {str(e)}", exc_info=True)
            return self.error_response(f"Error al obtener reclamos: {str(e)}", 500)
            
    def get_reclamo_por_orden(self, orden_id):
        try:
            int_orden_id = int(orden_id)
            response = self.model.find_all(filters={'orden_compra_id': int_orden_id}, limit=1)
            
            if response.get('success') and response.get('data'):
                return self.success_response(response['data'][0])
                
            return self.success_response(None, "No existe reclamo para esta orden.")
        except (ValueError, TypeError):
            return self.error_response(f"El ID de orden '{orden_id}' no es válido.", 400)
        except Exception as e:
            logger.error(f"Error al buscar reclamo por orden: {str(e)}", exc_info=True)
            return self.error_response(f"Error al buscar reclamo: {str(e)}", 500)

    def get_reclamo_with_details(self, reclamo_id):
        try:
            query = "*, proveedor:proveedores(nombre), orden:ordenes_compra(codigo_oc)"
            response = self.model.find_all(filters={'id': reclamo_id}, select_query=query, limit=1)

            if not response.get('success') or not response.get('data'):
                return self.error_response("Reclamo no encontrado.", 404)

            reclamo_data = response['data'][0]

            items_query = "*, insumo:insumos_catalogo(nombre)"
            items_response = self.item_model.find_all(filters={'reclamo_id': reclamo_id}, select_query=items_query)
            
            if items_response.get('success'):
                reclamo_data['items'] = items_response.get('data', [])
            else:
                reclamo_data['items'] = []

            return self.success_response(reclamo_data)
        except Exception as e:
            logger.error(f"Error obteniendo detalle del reclamo: {e}", exc_info=True)
            return self.error_response(f"Error inesperado: {str(e)}", 500)

    def cerrar_reclamo(self, reclamo_id, comentario):
        try:
            from datetime import datetime

            update_data = {
                'estado': 'CERRADO',
                'comentario_cierre': comentario,
                'fecha_cierre': datetime.now().isoformat()
            }
            
            response = self.model.update(reclamo_id, update_data)

            if response.get('success'):
                return self.success_response(response.get('data'), "Reclamo cerrado exitosamente.")
            else:
                return self.error_response(response.get('error', 'No se pudo cerrar el reclamo.'), 500)
        except Exception as e:
            logger.error(f"Error cerrando el reclamo: {e}", exc_info=True)
            return self.error_response(f"Error inesperado: {str(e)}", 500)
