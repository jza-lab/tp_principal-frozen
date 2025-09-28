from app.controllers.base_controller import BaseController
from app.models.orden_produccion import OrdenProduccionModel
from app.schemas.orden_produccion_schema import OrdenProduccionSchema
from typing import Dict, Optional, List
from marshmallow import ValidationError
from app.controllers.producto_controller import ProductoController
from app.controllers.receta_controller import RecetaController
from app.controllers.usuario_controller import UsuarioController

class OrdenProduccionController(BaseController):
    """
    Controlador para la lógica de negocio de las Órdenes de Producción.
    """

    def __init__(self):
        super().__init__()
        self.model = OrdenProduccionModel()
        self.schema = OrdenProduccionSchema()
        # Se instancian los controladores para obtener datos para los formularios
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
                # Si el modelo devuelve un error, lo propagamos
                error_msg = result.get('error', 'Error desconocido al obtener órdenes.')
                status_code = 404 if "no encontradas" in str(error_msg).lower() else 500
                return self.error_response(error_msg, status_code)
        except Exception as e:
            # Aquí capturamos cualquier excepción no esperada
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_orden_por_id(self, orden_id: int) -> Optional[Dict]:
        """
        Obtiene el detalle de una orden de producción específica.
        """
        result = self.model.get_one_enriched(orden_id)
        return result.get('data')

    def crear_orden(self, form_data: Dict, usuario_id: int) -> Dict:
        """
        Valida datos y crea una orden en estado PENDIENTE.
        La reserva de stock se hará en la aprobación.
        """
        try:
            validated_data = self.schema.load(form_data)

            # Añadir datos que no vienen del formulario
            validated_data['usuario_id'] = usuario_id
            validated_data['estado'] = 'PENDIENTE' # Estado inicial por defecto

            # Usar el método 'create' genérico del BaseModel
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

    def crear_orden_desde_planificacion(self, producto_id: int, pedidos_ids: List[int], usuario_id: int) -> Dict:
        """
        Orquesta la creación de una orden consolidada desde el módulo de planificación.
        """
        from models.pedido import PedidoModel
        from models.receta import RecetaModel
        from datetime import date

        pedido_model = PedidoModel()
        receta_model = RecetaModel()

        try:
            # 1. Calcular cantidad total
            pedidos = pedido_model.find_all({'id.in': tuple(pedidos_ids)}).get('data', [])
            if not pedidos:
                return {'success': False, 'error': 'No se encontraron los pedidos para consolidar.'}

            cantidad_total = sum(p['cantidad'] for p in pedidos)

            # 2. Encontrar receta activa
            receta_result = receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
            if not receta_result.get('data'):
                return {'success': False, 'error': f'No se encontró una receta activa para el producto ID {producto_id}.'}
            receta = receta_result['data'][0]

            # 3. Crear la orden de producción
            datos_orden = {
                'producto_id': producto_id,
                'cantidad': cantidad_total,
                'fecha_planificada': date.today(),
                'receta_id': receta['id'],
                'prioridad': 'NORMAL' # O determinarla según alguna lógica
            }
            resultado_creacion = self.crear_orden(datos_orden, usuario_id)

            if not resultado_creacion.get('success'):
                return resultado_creacion # Devolver el error de la creación

            # 4. Actualizar pedidos
            orden_creada = resultado_creacion['data']
            for pedido_id in pedidos_ids:
                pedido_model.update(pedido_id, {
                    'estado': 'PLANIFICADO',
                    'orden_produccion_id': orden_creada['id']
                })

            return {'success': True, 'data': orden_creada}

        except Exception as e:
            # Aquí se podría añadir un rollback si la creación de la orden falla a medio camino
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