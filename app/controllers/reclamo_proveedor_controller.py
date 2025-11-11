from app.models.reclamo_proveedor_model import ReclamoProveedorModel
from app.models.orden_compra_model import OrdenCompraModel
from app.schemas.reclamo_proveedor_schema import ReclamoProveedorSchema
from marshmallow import ValidationError
from app.controllers.base_controller import BaseController
from app.services.email_service import send_email
from flask import current_app
from app.controllers.proveedor_controller import ProveedorController
import logging

# Configurar un logger para este controlador
logger = logging.getLogger(__name__)

class ReclamoProveedorController(BaseController):
    def __init__(self):
        self.model = ReclamoProveedorModel()
        self.schema = ReclamoProveedorSchema()
        self.proveedor_controller = ProveedorController()
        self.orden_compra_model = OrdenCompraModel()

    def crear_reclamo(self, data):
        try:
            # --- INICIO VALIDACIÓN ---
            
            proveedor_id = data.get('proveedor_id')
            orden_compra_id_str = data.get('orden_compra_id')
            orden_compra_id_int = None

            # 1. Validar y convertir el ID de la Orden de Compra (si se proveyó)
            if orden_compra_id_str:
                try:
                    # Intentamos convertir el ID (que puede venir como string de un form)
                    orden_compra_id_int = int(orden_compra_id_str)
                except (ValueError, TypeError):
                    # Si no es un número válido (ej. "", "abc", None), fallamos con un error claro
                    logger.warning(f"Intento de crear reclamo con OC ID inválido: {orden_compra_id_str}")
                    return self.error_response(f"El ID de Orden de Compra '{orden_compra_id_str}' no es un número válido.", 400)

            # 2. Buscar el proveedor_id si falta, usando el orden_compra_id_int validado
            if not proveedor_id and orden_compra_id_int:
                logger.info(f"Buscando proveedor_id para OC ID: {orden_compra_id_int}")
                # Buscamos la orden
                orden_response = self.orden_compra_model.find_by_id(orden_compra_id_int)
                
                if orden_response.get('success') and orden_response.get('data'):
                    orden_data = orden_response['data']
                    proveedor_id = orden_data.get('proveedor_id') # ¡Encontrado!
                    logger.info(f"Proveedor_id {proveedor_id} encontrado desde la OC.")
                else:
                    # Si la orden no existe, no podemos seguir
                    logger.warning(f"No se encontró la OC ID {orden_compra_id_int} para obtener el proveedor.")
                    return self.error_response(f"No se pudo encontrar la orden de compra ID {orden_compra_id_int} para obtener el proveedor.", 404)

            # 3. Mapear los datos para el esquema
            datos_para_schema = {
                'orden_compra_id': orden_compra_id_int, # Usamos el ID numérico
                'proveedor_id': proveedor_id,           # Usamos el ID encontrado o el provisto
                'motivo': data.get('motivo') or data.get('titulo'),
                'descripcion_problema': data.get('descripcion_problema') or data.get('descripcion')
            }
            # --- FIN VALIDACIÓN ---

            # 4. Validar con Marshmallow (ahora sí debería tener proveedor_id)
            validated_data = self.schema.load(datos_para_schema)
            validated_data['estado'] = 'ABIERTO'

            # 5. Crear en la BD
            response = self.model.create(validated_data)
            
            if response and response.get('success'):
                
                # --- INICIO MODIFICACIÓN (FIX: KeyError: 0) ---
                # El traceback 'KeyError: 0' indica que 'data' es un diccionario, NO una lista.
                # El modelo devuelve el objeto creado directamente.
                # reclamo_creado = response.get('data')[0] # <-- ESTA LÍNEA DABA ERROR
                reclamo_creado = response.get('data') # <-- SOLUCIÓN: Quitar el [0]
                
                if not reclamo_creado:
                    logger.error("model.create tuvo éxito pero no devolvió 'data'")
                    return self.error_response("Error al obtener los datos del reclamo creado.", 500)
                # --- FIN MODIFICACIÓN ---
                
                proveedor_id_creado = reclamo_creado.get('proveedor_id')
                
                # 6. Enviar email (si se puede)
                proveedor_resp, _ = self.proveedor_controller.obtener_proveedor_por_id(proveedor_id_creado)
                
                if proveedor_resp.get('success'):
                    proveedor = proveedor_resp.get('data')
                    destinatario = proveedor.get('email')
                    if destinatario:
                        asunto = f"Nuevo Reclamo para Orden de Compra - ID {reclamo_creado.get('orden_compra_id')}"
                        cuerpo = f"""
                        <h1>Hola {proveedor.get('nombre')},</h1>
                        <p>Se ha generado un nuevo reclamo asociado a su cuenta.</p>
                        <p><strong>Título del Reclamo:</strong> {reclamo_creado.get('motivo')}</p>
                        <p><strong>Descripción:</strong></p>
                        <p>{reclamo_creado.get('descripcion_problema')}</p>
                        <p>Por favor, póngase en contacto para coordinar la resolución.</p>
                        <p>Saludos cordiales,<br>El Equipo de Frozen</p>
                        """
                        with current_app.app_context():
                            send_email(destinatario, asunto, cuerpo)

                return self.success_response(reclamo_creado, "Reclamo creado exitosamente")
            else:
                # Si la creación falla, devolver el error del modelo
                error_msg = response.get('error', 'Error desconocido al crear el reclamo en la base de datos.')
                logger.error(f"Error en model.create al crear reclamo: {error_msg}")
                return self.error_response(error_msg, 500)

        except ValidationError as e:
            # Error de validación de Marshmallow (ej. proveedor_id sigue nulo)
            logger.error(f"Error de validación (schema) al crear reclamo: {e.messages}")
            return self.error_response(e.messages, 400)
        except Exception as e:
            # Otros errores inesperados (aquí es donde caía el '0')
            logger.error(f"Error inesperado (catch-all) al crear reclamo: {e}", exc_info=True)
            return self.error_response(f"Error inesperado: {str(e)}", 500)

    def get_all_reclamos(self):
        try:
            enriched_query = "*, proveedor:proveedores(nombre), orden:ordenes_compra(codigo_oc)"
            reclamos = self.model.find_all(select=enriched_query, order_by={'created_at': 'desc'})
            
            if reclamos:
                return self.success_response(reclamos)
            
            return self.success_response([], "No se encontraron reclamos.")
        except Exception as e:
            logger.error(f"Error al obtener reclamos: {str(e)}", exc_info=True)
            return self.error_response(f"Error al obtener reclamos: {str(e)}", 500)
            
    def get_reclamo_por_orden(self, orden_id):
        try:
            # Asegurarnos que el ID sea int
            int_orden_id = int(orden_id)
            result = self.model.find_all(filters={'orden_compra_id': int_orden_id}, limit=1)
            if result:
                return self.success_response(result[0])
            return self.success_response(None, "No existe reclamo para esta orden.")
        except (ValueError, TypeError):
            return self.error_response(f"El ID de orden '{orden_id}' no es válido.", 400)
        except Exception as e:
            logger.error(f"Error al buscar reclamo por orden: {str(e)}", exc_info=True)
            return self.error_response(f"Error al buscar reclamo: {str(e)}", 500)