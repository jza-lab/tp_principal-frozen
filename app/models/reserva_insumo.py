from app.models.base_model import BaseModel
from typing import Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ReservaInsumoModel(BaseModel):
    """Modelo para la tabla reservas_insumos"""

    def get_table_name(self) -> str:
        return 'reservas_insumos'

    def get_consumo_total_valorizado_en_periodo(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Calcula el valor total de los insumos consumidos en un rango de fechas.
        Esto se aproxima al Costo de los Bienes Vendidos (COGS) para los insumos.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                'cantidad_reservada, lote:insumos_inventario(insumo:insumos_catalogo(precio_unitario))'
            ).eq('estado', 'CONSUMIDO').gte('created_at', fecha_inicio.isoformat()).lte('created_at', fecha_fin.isoformat())
            
            result = query.execute()

            if not result.data:
                return {'success': True, 'total_consumido_valorizado': 0}

            total_valorizado = 0
            for reserva in result.data:
                cantidad = reserva.get('cantidad_reservada', 0)
                precio = reserva.get('lote', {}).get('insumo', {}).get('precio_unitario', 0)
                if cantidad is not None and precio is not None:
                    total_valorizado += cantidad * precio
            
            return {'success': True, 'total_consumido_valorizado': total_valorizado}
        except Exception as e:
            logger.error(f"Error calculando consumo total valorizado de insumos: {str(e)}")
            return {'success': False, 'error': str(e), 'total_consumido_valorizado': 0}

    def get_consumo_promedio_diario_por_insumo(self, insumo_id: str, dias_periodo: int = 30) -> Dict:
        """
        Calcula el consumo promedio diario de un insumo específico en los últimos X días.
        """
        from datetime import timedelta

        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=dias_periodo)

        try:
            # Necesitamos hacer un join manual a través de las tablas.
            # 1. Obtener los lotes del insumo
            lotes_res = self.db.table('insumos_inventario').select('id_lote').eq('id_insumo', insumo_id).execute()
            if not lotes_res.data:
                return {'success': True, 'consumo_promedio_diario': 0}
            
            lote_ids = [lote['id_lote'] for lote in lotes_res.data]

            # 2. Obtener las reservas consumidas de esos lotes
            query = self.db.table(self.get_table_name()).select('cantidad_reservada').eq('estado', 'CONSUMIDO').in_('lote_insumo_id', lote_ids).gte('created_at', fecha_inicio.isoformat()).lte('created_at', fecha_fin.isoformat())
            
            consumo_res = query.execute()

            if not consumo_res.data:
                return {'success': True, 'consumo_promedio_diario': 0}
            
            total_consumido = sum(item.get('cantidad_reservada', 0) for item in consumo_res.data)
            consumo_promedio_diario = total_consumido / dias_periodo

            return {'success': True, 'consumo_promedio_diario': consumo_promedio_diario}
        except Exception as e:
            logger.error(f"Error calculando consumo promedio diario para el insumo {insumo_id}: {str(e)}")
            return {'success': False, 'error': str(e), 'consumo_promedio_diario': 0}

    def get_by_orden_produccion_id(self, orden_produccion_id: int) -> Dict:
        """
        Obtiene todas las reservas de insumos para una orden de producción específica.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*').eq('orden_produccion_id', orden_produccion_id)
            result = query.execute()

            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}
        except Exception as e:
            logger.error(f"Error al obtener reservas por ID de orden de producción {orden_produccion_id}: {str(e)}")
            return {'success': False, 'error': str(e), 'data': []}
