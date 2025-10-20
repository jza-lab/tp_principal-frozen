# app/models/lote_producto.py
from datetime import date, datetime, timedelta
from app.models.base_model import BaseModel
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class LoteProductoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de lotes_productos.
    """

    def get_table_name(self) -> str:
        return 'lotes_productos'

    def find_by_numero_lote(self, numero_lote: str) -> Dict:
        """Busca un lote por su número de lote único."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('numero_lote', numero_lote).single().execute()
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': 'Lote no encontrado'}
        except Exception as e:
            if "Missing data" in str(e):
                 return {'success': False, 'error': 'Lote no encontrado'}
            logger.error(f"Error buscando lote por número: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_by_producto_id(self, producto_id: int) -> Dict:
        """Busca todos los lotes de un producto específico."""
        try:
            result = self.db.table(self.get_table_name()).select('*').eq('producto_id', producto_id).execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes por producto: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_lotes_disponibles(self) -> Dict:
        """Busca lotes disponibles (no vencidos y con stock)."""
        try:
            result = (
                self.db.table(self.get_table_name())
                .select('*')
                .eq('estado', 'DISPONIBLE')
                .gt('cantidad_actual', 0)
                .execute()
            )
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando lotes disponibles: {str(e)}")
            return {'success': False, 'error': str(e)}


    # --- MÉTODO NUEVO A AÑADIR ---
    def get_all_lotes_for_view(self):
        """
        Obtiene todos los lotes de productos con datos enriquecidos (nombre del producto)
        para ser mostrados en la vista de listado.
        """
        try:
            result = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre)'
            ).order('created_at', desc=True).execute()

            # Aplanar los resultados para un uso más fácil en la plantilla
            flat_data = []
            for item in result.data:
                if item.get('producto'):
                    item['producto_nombre'] = item['producto']['nombre']
                else:
                    item['producto_nombre'] = 'Producto no encontrado'
                del item['producto']
                flat_data.append(item)

            return {'success': True, 'data': flat_data}
        except Exception as e:
            logger.error(f"Error obteniendo lotes de productos para la vista: {e}")
            return {'success': False, 'error': str(e)}

    def get_lote_detail_for_view(self, id_lote: int):
        """
        Obtiene el detalle de un lote de producto con datos enriquecidos.
        """
        try:
            # --- LÍNEA CORREGIDA ---
            # Cambiamos 'id' por 'id_lote' para que coincida con la columna de la base de datos.
            result = self.db.table(self.get_table_name()).select(
                '*, producto:productos(nombre, codigo)'
            ).eq('id_lote', id_lote).single().execute()
            # ------------------------

            if result.data:
                item = result.data
                if item.get('producto'):
                    item['producto_nombre'] = item['producto']['nombre']
                    item['producto_codigo'] = item['producto']['codigo']
                else:
                    item['producto_nombre'] = 'Producto no encontrado'
                    item['producto_codigo'] = 'N/A'
                del item['producto']
                return {'success': True, 'data': item}
            else:
                return {'success': False, 'error': 'Lote no encontrado'}
        except Exception as e:
            logger.error(f"Error obteniendo detalle de lote de producto {id_lote}: {e}")
            return {'success': False, 'error': str(e)}
        
    def update_lote_cantidad_por_despacho(self, lote_id: int, cantidad_despachada: float) -> dict:
        """
        Reduce la cantidad_actual y la cantidad_reservada de un lote 
        al completar un pedido.
        """
        try:
            # 1. Obtener el lote para verificar el stock
            lote_result = self.find_by_id(lote_id)
            if not lote_result.get('data'):
                return {'success': False, 'error': f"Lote de producto ID {lote_id} no encontrado."}
            
            lote = lote_result['data']
            
            # 2. Calcular nuevas cantidades (deben ser >= 0)
            cantidad_actual_nueva = lote.get('cantidad_actual', 0.0) - cantidad_despachada
            cantidad_reservada_nueva = lote.get('cantidad_reservada', 0.0) - cantidad_despachada
            
            if cantidad_actual_nueva < 0 or cantidad_reservada_nueva < 0:
                # Esto no debería ocurrir si el sistema de reservas funciona bien, pero es una protección
                return {'success': False, 'error': 'Intento de despachar más cantidad de la reservada o disponible en el lote.'}

            # 3. Datos a actualizar
            update_data = {
                'cantidad_actual': cantidad_actual_nueva,
                'cantidad_reservada': cantidad_reservada_nueva,
                'fecha_actualizacion': datetime.now().isoformat()
            }
            
            # 4. Actualizar en la base de datos
            # Asumo que self.update() es el método de la clase base para actualizar el registro en la DB
            update_result = self.update(lote_id, update_data, 'id') 
            
            if update_result.get('success'):
                return {'success': True, 'data': update_result['data']}
            else:
                return {'success': False, 'error': update_result.get('error', 'Error desconocido al actualizar lote.')}

        except Exception as e:
            logger.error(f"Error al despachar lote {lote_id}: {str(e)}")
            return {'success': False, 'error': f"Error interno en la BD al actualizar lote: {str(e)}"}
        
    def find_por_vencimiento(self, dias_adelante: int = 7) -> Dict:
        """Obtener lotes de productos que vencen en X días"""
        try:
            fecha_limite = (date.today() + timedelta(days=dias_adelante)).isoformat()
            fecha_hoy = date.today().isoformat()

            result = (self.db.table(self.table_name)
                     .select('*, producto:productos(nombre)')
                     .gte('fecha_vencimiento', fecha_hoy)
                     .lte('fecha_vencimiento', fecha_limite)
                     .eq('estado', 'DISPONIBLE')
                     .order('fecha_vencimiento')
                     .execute())

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes de productos por vencimiento: {str(e)}")
            return {'success': False, 'error': str(e)}