from app.models.base_model import BaseModel
from typing import Dict, List
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class InsumoInventarioModel(BaseModel):
    """Modelo para la tabla insumos_inventario"""

    def get_table_name(self) -> str:
        return 'insumos_inventario'

    def get_all_lotes_for_view(self) -> Dict:
        """
        Obtiene todos los lotes de insumos con su fecha de ingreso, cantidad y precio,
        listos para ser usados en vistas o reportes.
        """
        try:
            # Corregido: 'fecha_ingreso' no existe, se usa 'created_at' que es la fecha de creación del lote.
            # Se renombra en el resultado para mantener la consistencia con lo que espera el controlador.
            query = self.db.table(self.get_table_name()).select(
                'created_at,cantidad_actual'
            ).gt('cantidad_actual', 0) # Solo lotes con stock

            result = query.execute()

            if result.data:
                # Renombrar 'cantidad_actual' a 'cantidad' y 'created_at' a 'fecha_ingreso'
                for lote in result.data:
                    lote['cantidad'] = lote.pop('cantidad_actual')
                    lote['fecha_ingreso'] = lote.pop('created_at')
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error obteniendo lotes de insumo para la vista: {str(e)}")
            return {'success': False, 'error': str(e)}


    def get_stock_total_valorizado(self, fecha: date = None) -> Dict:
        """
        Calcula el valor total del inventario de insumos en una fecha específica.
        Si la fecha es None, calcula el valor actual.
        """
        try:
            # Por ahora, simplificamos y obtenemos el stock actual valorizado
            # ya que no tenemos un historial de movimientos para calcularlo a una fecha pasada.
            query = self.db.table(self.get_table_name()).select(
                'cantidad_actual, insumo:insumos_catalogo(precio_unitario)'
            ).gt('cantidad_actual', 0)

            result = query.execute()

            if not result.data:
                return {'success': True, 'total_valorizado': 0}

            total_valorizado = 0
            for lote in result.data:
                cantidad = lote.get('cantidad_actual', 0)
                precio = lote.get('insumo', {}).get('precio_unitario', 0)
                if cantidad is not None and precio is not None:
                    total_valorizado += cantidad * precio
            
            return {'success': True, 'total_valorizado': total_valorizado}
        except Exception as e:
            logger.error(f"Error calculando stock total valorizado de insumos: {str(e)}")
            return {'success': False, 'error': str(e), 'total_valorizado': 0}

    def get_costo_promedio_ponderado(self, insumo_id: int) -> Dict:
        """
        Calcula el costo promedio ponderado para un insumo específico.
        Costo Promedio = Sum(cantidad_lote * precio_compra_lote) / Sum(cantidad_lote)
        """
        try:
            lotes_res = self.find_all(filters={'id_insumo': insumo_id})
            if not lotes_res.get('success') or not lotes_res.get('data'):
                return {'success': False, 'error': 'No se encontraron lotes para el insumo.'}

            lotes = lotes_res['data']
            
            valor_total = 0
            cantidad_total = 0

            for lote in lotes:
                cantidad = float(lote.get('cantidad', 0))
                precio = float(lote.get('precio_unitario') or 0.0) # Usar 0 si es None
                if cantidad > 0:
                    valor_total += cantidad * precio
                    cantidad_total += cantidad
            
            if cantidad_total == 0:
                return {'success': True, 'costo_promedio': 0.0}

            costo_promedio = valor_total / cantidad_total
            return {'success': True, 'costo_promedio': costo_promedio}

        except Exception as e:
            logger.error(f"Error calculando costo promedio ponderado para insumo {insumo_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_stock_actual_por_insumo(self, insumo_id: str) -> Dict:
        """
        Obtiene el stock actual total para un insumo específico sumando todos sus lotes.
        """
        try:
            query = self.db.table(self.get_table_name()).select('cantidad_actual').eq('id_insumo', insumo_id)
            result = query.execute()
            
            if not result.data:
                return {'success': True, 'stock_actual': 0}

            stock_total = sum(item.get('cantidad_actual', 0) for item in result.data)
            return {'success': True, 'stock_actual': stock_total}
        except Exception as e:
            logger.error(f"Error obteniendo stock actual para el insumo {insumo_id}: {str(e)}")
            return {'success': False, 'error': str(e), 'stock_actual': 0}

    def get_costos_promedio_ponderado_bulk(self, insumo_ids: List[str]) -> Dict:
        """
        Calcula el costo promedio ponderado para una lista de insumos en una sola consulta.
        Retorna un diccionario mapeando id_insumo -> costo_promedio.
        """
        if not insumo_ids:
            return {'success': True, 'data': {}}
        
        try:
            # Trae todos los lotes para los insumos solicitados que tengan cantidad y precio.
            result = self.db.table(self.get_table_name()).select(
                'id_insumo, cantidad_actual, precio_unitario'
            ).in_('id_insumo', insumo_ids).gt('cantidad_actual', 0).execute()

            if not result.data:
                return {'success': True, 'data': {}}

            # Agrupa los lotes por insumo_id
            lotes_por_insumo = {}
            for lote in result.data:
                insumo_id = lote['id_insumo']
                if insumo_id not in lotes_por_insumo:
                    lotes_por_insumo[insumo_id] = []
                lotes_por_insumo[insumo_id].append(lote)
            
            # Calcula el costo promedio para cada insumo
            costos_promedio = {}
            for insumo_id, lotes in lotes_por_insumo.items():
                valor_total = sum(float(l.get('cantidad_actual', 0)) * float(l.get('precio_unitario') or 0.0) for l in lotes)
                cantidad_total = sum(float(l.get('cantidad_actual', 0)) for l in lotes)
                
                if cantidad_total > 0:
                    costos_promedio[insumo_id] = valor_total / cantidad_total
                else:
                    costos_promedio[insumo_id] = 0.0
            
            return {'success': True, 'data': costos_promedio}

        except Exception as e:
            logger.error(f"Error calculando costos promedio ponderado bulk: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
