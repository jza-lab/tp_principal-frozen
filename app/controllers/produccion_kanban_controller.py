# app/controllers/produccion_kanban_controller.py
import logging
from collections import defaultdict
from app.controllers.base_controller import BaseController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.utils.estados import OP_KANBAN_COLUMNAS

logger = logging.getLogger(__name__)

class ProduccionKanbanController(BaseController):
    def __init__(self):
        super().__init__()
        self.orden_produccion_controller = OrdenProduccionController()

    def obtener_datos_para_tablero(self, usuario_id: int, usuario_rol: str) -> tuple:
        """
        Orquesta la obtención de todos los datos necesarios para el tablero Kanban.
        Incluye la lógica de filtrado de OPs y de columnas según el rol.
        """
        try:
            # 1. Obtener las OPs del día
            response_ops, _ = self.orden_produccion_controller.obtener_ordenes_para_kanban_hoy()
            if not response_ops.get('success'):
                return self.error_response("Error al cargar las órdenes para el tablero.")

            ordenes = response_ops.get('data', [])
            
            # 2. Agrupar por estado (lógica movida desde el antiguo controller)
            ordenes_por_estado = defaultdict(list)
            for orden in ordenes:
                # Normalizar el estado de la BD (con espacios) al formato de constante (con guion bajo)
                estado_db = orden.get('estado', '').strip()
                estado_constante = estado_db.replace(' ', '_')

                if estado_constante in ['EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'EN_PRODUCCION']:
                    estado_constante = 'EN_PROCESO'
                
                if estado_constante in OP_KANBAN_COLUMNAS:
                    ordenes_por_estado[estado_constante].append(orden)

            # 3. Determinar qué columnas mostrar (lógica movida desde la ruta)
            columnas = OP_KANBAN_COLUMNAS
            if usuario_rol == 'OPERARIO':
                columnas = {
                    'LISTA_PARA_PRODUCIR': 'Lista para Producir',
                    'EN_PROCESO': 'En Proceso'
                }
            
            # 4. Ensamblar el contexto para la plantilla
            contexto = {
                'ordenes_por_estado': dict(ordenes_por_estado),
                'columnas': columnas,
                'usuario_rol': usuario_rol
            }
            return self.success_response(data=contexto)

        except Exception as e:
            logger.error(f"Error crítico al obtener datos para el tablero Kanban: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def mover_orden(self, op_id: int, nuevo_estado: str, user_role: str) -> tuple:
        """
        Orquesta el cambio de estado de una OP en el Kanban, validando permisos.
        """
        if not nuevo_estado:
            return self.error_response("El 'nuevo_estado' es requerido.", 400)

        try:
            op_actual_res = self.orden_produccion_controller.obtener_orden_por_id(op_id)
            if not op_actual_res.get('success'):
                return self.error_response("Orden de Producción no encontrada.", 404)
            estado_actual = op_actual_res['data'].get('estado')

            # Aquí se pueden añadir validaciones de transición específicas del Kanban si es necesario
            # Por ejemplo, un operario solo puede mover a ciertos estados.
            # Esta lógica es un ejemplo y puede ser ajustada.
            if user_role == 'OPERARIO':
                allowed_transitions = {
                    'LISTA_PARA_PRODUCIR': ['EN_PROCESO'],
                    'EN_PROCESO': ['CONTROL_DE_CALIDAD'] # Ejemplo
                }
                if estado_actual not in allowed_transitions or nuevo_estado not in allowed_transitions[estado_actual]:
                    return self.error_response(f"Movimiento de '{estado_actual}' a '{nuevo_estado}' no permitido.", 403)

            # Se delega el cambio de estado al controlador principal de OPs.
            # Usamos el método simple ya que el Kanban maneja estados intermedios.
            resultado = self.orden_produccion_controller.cambiar_estado_orden_simple(op_id, nuevo_estado)
            
            if resultado.get('success'):
                return self.success_response(data=resultado.get('data'))
            else:
                return self.error_response(resultado.get('error', 'Error al cambiar el estado.'), 500)

        except Exception as e:
            logger.error(f"Error crítico en mover_orden (Kanban) para OP {op_id}: {e}", exc_info=True)
            return self.error_response(f"Error interno: {str(e)}", 500)

    def obtener_estado_produccion(self, op_id: int) -> tuple:
        """
        Obtiene el estado de producción en tiempo real para una OP.
        Delega la llamada al controlador de órdenes de producción.
        """
        try:
            return self.orden_produccion_controller.obtener_estado_produccion_op(op_id)
        except Exception as e:
            logger.error(f"Error al obtener estado de producción para OP {op_id} desde KanbanController: {e}", exc_info=True)
            return self.error_response(f"Error interno al consultar estado: {str(e)}", 500)
