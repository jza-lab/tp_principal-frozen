from app.controllers.base_controller import BaseController
from app.models.pedido import PedidoModel
from app.models.producto import ProductoModel
from app.schemas.pedido_schema import PedidoSchema
from typing import Dict, Optional
from marshmallow import ValidationError

class PedidoController(BaseController):
    """
    Controlador para la lógica de negocio de los Pedidos de Venta.
    """

    def __init__(self):
        super().__init__()
        self.model = PedidoModel()
        self.schema = PedidoSchema()
        # Necesitamos el modelo de producto para obtener la lista de productos para el formulario.
        self.producto_model = ProductoModel()

    def obtener_pedidos(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene una lista de pedidos, aplicando filtros.
        """
        try:
            result = self.model.get_all_with_items(filtros)
            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener pedidos.')
                return self.error_response(error_msg, 500)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_pedido_por_id(self, pedido_id: int) -> tuple:
        """
        Obtiene el detalle de un pedido específico con sus items.
        """
        try:
            result = self.model.get_one_with_items(pedido_id)
            if result.get('success'):
                return self.success_response(data=result.get('data'))
            else:
                error_msg = result.get('error', 'Error desconocido.')
                status_code = 404 if "no encontrado" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)
            
    def crear_pedido_con_items(self, form_data: Dict) -> tuple:
        """
        Valida y crea un nuevo pedido con sus items.
        """
        try:
            # ----------------------------------------------------------------------
            # !!! CORRECCIÓN CRÍTICA PARA EL ERROR DE 'Unknown field' !!!
            # El campo 'items-TOTAL_FORMS' es un campo de gestión de formularios 
            # dinámicos de WTForms/JS. Marshmallow no lo conoce y lo rechaza.
            # Lo eliminamos antes de pasar los datos al schema.
            if 'items-TOTAL_FORMS' in form_data:
                # Usamos .pop() para eliminar la clave del diccionario antes de la carga.
                form_data.pop('items-TOTAL_FORMS')
            # ----------------------------------------------------------------------

            # 1. Validar el payload completo
            # Nota: Si estás usando Flask-WTF, es posible que el error ocurra antes de esta línea.
            # Asumimos que form_data ya es un diccionario simple (dict) con los datos del formulario.
            validated_data = self.schema.load(form_data)
            
            # 2. Separar datos del pedido y datos de los items
            items_data = validated_data.pop('items')
            pedido_data = validated_data
            
            # Establecer estado inicial si no se proporciona
            if 'estado' not in pedido_data:
                pedido_data['estado'] = 'PENDIENTE'

            # 3. Llamar al método del modelo
            result = self.model.create_with_items(pedido_data, items_data)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Pedido creado con éxito.", status_code=201)
            else:
                return self.error_response(result.get('error', 'No se pudo crear el pedido.'), 400)

        except ValidationError as e:
            # Si el error es de Marshmallow, se captura aquí.
            return self.error_response(f"Datos inválidos: {e.messages}", 400)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_pedido_con_items(self, pedido_id: int, form_data: Dict) -> tuple:
        """
        Valida y actualiza un pedido existente y sus items.
        """
        try:
            # ----------------------------------------------------------------------
            # !!! CORRECCIÓN CRÍTICA PARA EL ERROR DE 'Unknown field' en actualización !!!
            if 'items-TOTAL_FORMS' in form_data:
                form_data.pop('items-TOTAL_FORMS')
            # ----------------------------------------------------------------------
            
            # 1. Validar el payload completo
            validated_data = self.schema.load(form_data)

            # 2. Separar datos del pedido y datos de los items
            items_data = validated_data.pop('items')
            pedido_data = validated_data

            # 3. Llamar al método del modelo
            result = self.model.update_with_items(pedido_id, pedido_data, items_data)

            if result.get('success'):
                return self.success_response(data=result.get('data'), message="Pedido actualizado con éxito.")
            else:
                return self.error_response(result.get('error', 'No se pudo actualizar el pedido.'), 400)
            
        except ValidationError as e:
            return self.error_response(f"Datos inválidos: {e.messages}", 400)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)
            
    def cancelar_pedido(self, pedido_id: int) -> tuple:
        """
        Cambia el estado de un pedido a 'CANCELADO'.
        """
        try:
            # Verificar que el pedido existe antes de intentar cambiar el estado
            pedido_existente = self.model.get_one_with_items(pedido_id)
            if not pedido_existente.get('success'):
                 return self.error_response(f"Pedido con ID {pedido_id} no encontrado.", 404)
            
            result = self.model.cambiar_estado(pedido_id, 'CANCELADO')
            if result.get('success'):
                return self.success_response(message="Pedido cancelado con éxito.")
            else:
                return self.error_response(result.get('error', 'Error al cancelar el pedido.'), 500)
        except Exception as e:
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_datos_para_formulario(self) -> tuple:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de pedidos.
        """
        try:
            # Usamos el modelo de producto para obtener todos los productos.
            # El modelo de producto devuelve un dict, accedemos a la clave 'data'.
            productos_result = self.producto_model.find_all(order_by='nombre')
            if productos_result.get('success'):
                productos = productos_result.get('data', [])
                # Devolvemos solo los datos necesarios, no toda la respuesta del controlador.
                return self.success_response(data={'productos': productos})
            else:
                return self.error_response("Error al obtener la lista de productos.", 500)
        except Exception as e:
            return self.error_response(f'Error interno obteniendo datos para el formulario: {str(e)}', 500)
