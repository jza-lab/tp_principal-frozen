from app.controllers.base_controller import BaseController
from app.models.costo_fijo import CostoFijoModel
from flask_jwt_extended import get_jwt_identity
import logging

logger = logging.getLogger(__name__)

class CostoFijoController(BaseController):
    """
    Controlador para gestionar la lógica de negocio de los costos fijos.
    """
    def __init__(self):
        super().__init__()
        self.model = CostoFijoModel()

    def get_costo_fijo_by_id(self, costo_fijo_id):
        """
        Obtiene un costo fijo por su ID.
        """
        result = self.model.find_by_id(costo_fijo_id)
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Costo fijo no encontrado.'), 404)

    def get_all_costos_fijos(self, filters=None):
        """
        Obtiene todos los costos fijos, opcionalmente aplicando filtros.
        """
        result = self.model.find_all(filters=filters)
        if result.get('success'):
            return self.success_response(result['data'])
        return self.error_response(result.get('error', 'Error al obtener los costos fijos.'))

    def create_costo_fijo(self, data):
        """
        Crea un nuevo registro de costo fijo.
        """
        # Aquí se podría añadir validación con un schema de Marshmallow.
        result = self.model.create(data)
        if result.get('success'):
            return self.success_response(result['data'], "Costo fijo creado exitosamente.", 201)
        return self.error_response(result.get('error', 'No se pudo crear el costo fijo.'))

    def update_costo_fijo(self, costo_fijo_id, data):
        """
        Actualiza un costo fijo existente y registra el cambio en el historial.
        """
        try:
            # 1. Obtener el valor actual antes de actualizar
            costo_actual_res = self.model.find_by_id(costo_fijo_id)
            if not costo_actual_res.get('success'):
                return self.error_response("Costo fijo no encontrado.", 404)
            
            monto_anterior = float(costo_actual_res['data'].get('monto_mensual', 0))
            
            # 2. Realizar la actualización
            result = self.model.update(costo_fijo_id, data)
            if not result.get('success'):
                return self.error_response(result.get('error', 'No se pudo actualizar el costo fijo.'))

            # 3. Registrar en historial si el monto cambió
            nuevo_monto = float(data.get('monto_mensual', monto_anterior))
            
            if abs(nuevo_monto - monto_anterior) > 0.01:
                usuario_id = get_jwt_identity()
                historial_data = {
                    'costo_fijo_id': costo_fijo_id,
                    'monto_anterior': monto_anterior,
                    'monto_nuevo': nuevo_monto,
                    'usuario_id': usuario_id
                }
                self.model.db.table('historial_costos_fijos').insert(historial_data).execute()

            return self.success_response(result['data'], "Costo fijo actualizado exitosamente.")

        except Exception as e:
            logger.error(f"Error en update_costo_fijo: {e}")
            return self.error_response(f"Error interno: {str(e)}", 500)

    def delete_costo_fijo(self, costo_fijo_id):
        """
        Desactiva un costo fijo (soft delete).
        """
        result = self.model.delete(costo_fijo_id, soft_delete=True)
        if result.get('success'):
            return self.success_response(message="Costo fijo desactivado exitosamente.")
        return self.error_response(result.get('error', 'No se pudo desactivar el costo fijo.'))
    
    def reactivate_costo_fijo(self, costo_fijo_id):
            """
            Reactiva un costo fijo (undo soft delete).
            """
            # Forzamos el update del campo 'activo' a True
            result = self.model.update(costo_fijo_id, {'activo': True})
            
            if result.get('success'):
                return self.success_response(message="Costo fijo reactivado exitosamente.")
            return self.error_response(result.get('error', 'No se pudo reactivar el costo fijo.'))

    def get_historial(self, costo_fijo_id):
        """
        Obtiene el historial de cambios de un costo fijo.
        """
        try:
            result = self.model.db.table('historial_costos_fijos')\
                .select('*, usuario:usuarios(nombre, apellido)')\
                .eq('costo_fijo_id', costo_fijo_id)\
                .order('fecha_cambio', desc=True)\
                .execute()
            
            if result.data is not None:
                return self.success_response(result.data)
            return self.error_response("No se pudo obtener el historial.", 500)
        except Exception as e:
            logger.error(f"Error obteniendo historial de costo fijo {costo_fijo_id}: {e}")
            return self.error_response(str(e), 500)

    def agregar_registro_historial(self, costo_fijo_id, data):
        """
        Agrega un registro histórico manual para un costo fijo por mes.
        Formato de fecha esperado: YYYY-MM
        """
        try:
            mes_anio = data.get('fecha') # YYYY-MM
            monto = data.get('monto')
            
            if not mes_anio or not monto:
                return self.error_response("Mes y monto son requeridos.", 400)

            # Convertir YYYY-MM a YYYY-MM-01
            fecha_completa = f"{mes_anio}-01 00:00:00"

            usuario_id = get_jwt_identity()
            
            # Intentar obtener el valor anterior más cercano para este costo (opcional, para UX)
            # Por ahora usamos 0 o el valor actual como 'anterior' ya que es una inserción manual
            # y lo que importa es el valor FIJADO en esa fecha.
            monto_anterior = 0 
            
            historial_data = {
                'costo_fijo_id': costo_fijo_id,
                'monto_anterior': monto_anterior, 
                'monto_nuevo': float(monto),
                'fecha_cambio': fecha_completa,
                'usuario_id': usuario_id
            }
            
            result = self.model.db.table('historial_costos_fijos').insert(historial_data).execute()
            
            if result.data:
                return self.success_response(result.data[0], "Registro mensual agregado.")
            return self.error_response("No se pudo guardar el registro mensual.")

        except Exception as e:
            logger.error(f"Error agregando historial manual: {e}")
            return self.error_response(str(e), 500)
