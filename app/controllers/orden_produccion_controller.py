from app.controllers.base_controller import BaseController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from app.controllers.producto_controller import ProductoController
from app.controllers.receta_controller import RecetaController
from app.controllers.usuario_controller import UsuarioController
from datetime import datetime

class OrdenProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las Órdenes de Producción.
    """

    def __init__(self):
        super().__init__()
        self.model = OrdenProduccionModel()
        self.schema = OrdenProduccionSchema()
        
        self.producto_controller = ProductoController()
        self.receta_controller = RecetaController()
        self.usuario_controller = UsuarioController()

    def obtener_ordenes(self, filtros: Optional[Dict] = None) -> tuple:
        """
        Obtiene una lista de órdenes de producción, aplicando filtros.
        Devuelve una tupla en formato (datos, http_status_code).
        """
        try:
            result = self.model.get_all_enriched(filtros)

            if result.get('success'):
                return self.success_response(data=result.get('data', []))
            else:
                error_msg = result.get('error', 'Error desconocido al obtener órdenes.')
                status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_orden_por_id(self, orden_id: int) -> Optional[Dict]:
        """
        Obtiene el detalle de una orden de producción específica.
        """
        result = self.model.get_one_enriched(orden_id)
        return result

    def obtener_desglose_origen(self, orden_id: int) -> Dict:
        """
        Obtiene los items de pedido que componen una orden de producción.
        """
        return self.model.obtener_desglose_origen(orden_id)

# app/controllers/orden_produccion_controller.py

    def crear_orden(self, form_data: Dict, usuario_id: int) -> Dict:
        """
        Valida datos y crea una orden en estado PENDIENTE,
        guardando el ID del operario en el campo usuario_creador_id si está asignado.
        """
        from app.models.receta import RecetaModel
        receta_model = RecetaModel()

        try:
            # Extraer producto_id y limpiar datos que gestiona el servidor
            producto_id = form_data.get('producto_id')
            if not producto_id:
                return {'success': False, 'error': 'El campo producto_id es requerido.'}

            # Mapear 'cantidad' del formulario a 'cantidad_planificada' del esquema
            if 'cantidad' in form_data:
                form_data['cantidad_planificada'] = form_data.pop('cantidad')
            
            # Obtener el ID del operario del formulario
            operario_asignado_id = form_data.pop('operario_asignado', None)
            # Quitar campos que no deben venir del cliente para la validación
            # Este paso es importante para evitar el error 'Unknown field'
            form_data.pop('usuario_id', None)
            form_data.pop('estado', None)
            form_data.pop('receta_id', None)

            # Lógica de negocio: Encontrar la receta activa para el producto
            receta_result = receta_model.find_all({
                'producto_id': int(producto_id),
                'activa': True
            }, limit=1)

            if not receta_result.get('success') or not receta_result.get('data'):
                return {'success': False, 'error': f'No se encontró una receta activa para el producto seleccionado (ID: {producto_id}).'}
            
            receta = receta_result['data'][0]
            form_data['receta_id'] = receta['id']

            # Validar los datos (ahora limpios) con el esquema
            validated_data = self.schema.load(form_data)
            
            # Añadir datos que no vienen del formulario.
            validated_data['codigo'] = f"OP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            validated_data['estado'] = 'PENDIENTE'
            
            # LÓGICA CLAVE: Asignar el ID del operario al campo 'usuario_creador_id'
            if operario_asignado_id:
                validated_data['usuario_creador_id'] = int(operario_asignado_id)
            else:
                validated_data['usuario_creador_id'] = usuario_id # Si no se asigna, usa el tuyo

            return self.model.create(validated_data)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def aprobar_orden(self, orden_id: int, usuario_id: int) -> Dict:
        """
        Aprueba una orden, reserva el stock y cambia el estado a APROBADA.
        """
        # Esta lógica debería idealmente estar en una función RPC en la BD
        # para asegurar la atomicidad. Por ahora, se simula aquí.
        # Se necesita un método en el modelo para manejar esto.
        # return self.model.aprobar_y_reservar(orden_id, usuario_id)
        # Como no tenemos el método del modelo, lo simulamos cambiando el estado.
        return self.model.cambiar_estado(orden_id, 'APROBADA')

    def rechazar_orden(self, orden_id: int, motivo: str) -> Dict:
        """
        Rechaza una orden, cambiando su estado a CANCELADA.
        """
        return self.model.cambiar_estado(orden_id, 'CANCELADA', observaciones=f"Rechazada: {motivo}")

    def cambiar_estado_orden(self, orden_id: int, nuevo_estado: str) -> Dict:
        """
        Cambia el estado de una orden (ej. 'EN_PROCESO', 'COMPLETADA').
        """
        return self.model.cambiar_estado(orden_id, nuevo_estado)

    def crear_orden_desde_planificacion(self, producto_id: int, item_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la creación de una orden consolidada desde el módulo de planificación.
        CORREGIDO: Opera sobre item_ids y actualiza los ítems en lote.
        """
        from app.models.pedido import PedidoModel
        from app.models.receta import RecetaModel
        from datetime import date

        pedido_model = PedidoModel()
        receta_model = RecetaModel()

        try:
            # 1. Obtener los ítems y calcular la cantidad total
            items_result = pedido_model.find_all_items(filters={'id': ('in', item_ids)})
            if not items_result.get('success') or not items_result.get('data'):
                return {'success': False, 'error': 'No se encontraron los ítems de pedido para consolidar.'}
            
            items = items_result['data']
            cantidad_total = sum(item['cantidad'] for item in items)

            # 2. Encontrar receta activa
            receta_result = receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
            if not receta_result.get('data'):
                return {'success': False, 'error': f'No se encontró una receta activa para el producto ID {producto_id}.'}
            receta = receta_result['data'][0]

            # 3. Crear la orden de producción
            datos_orden = {
                'producto_id': producto_id,
                'cantidad_planificada': cantidad_total, 
                'fecha_planificada': date.today().isoformat(),
                'receta_id': receta['id'],
                'prioridad': 'NORMAL'
            }
            resultado_creacion = self.crear_orden(datos_orden, usuario_id)

            if not resultado_creacion.get('success'):
                return resultado_creacion 

            # 4. Actualizar los ítems de pedido en lote
            orden_creada = resultado_creacion['data']
            update_data = {
                'estado': 'PLANIFICADO',
                'orden_produccion_id': orden_creada['id']
            }
            pedido_model.update_items(item_ids, update_data)

            return {'success': True, 'data': orden_creada}

        except Exception as e:
            return {'success': False, 'error': f'Error en el proceso de consolidación: {str(e)}'}


    def obtener_datos_para_formulario(self) -> Dict:
        """
        Obtiene los datos necesarios para popular los menús desplegables
        en el formulario de creación/edición de órdenes, usando los nuevos controladores.
        """
        try:
            productos = self.producto_controller.obtener_todos_los_productos()
            recetas = self.receta_controller.obtener_recetas({'activa': True})
            todos_los_usuarios = self.usuario_controller.obtener_todos()
            operarios = [u for u in todos_los_usuarios if u.get('rol') in ['OPERARIO', 'SUPERVISOR']]

            return {
                'productos': productos,
                'recetas': recetas,
                'operarios': operarios
            }
        except Exception as e:
            return {
                'productos': [], 'recetas': [], 'operarios': [],
                'error': f'Error obteniendo datos para el formulario: {str(e)}'
            }