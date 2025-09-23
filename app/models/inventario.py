from app.models.base_model import BaseModel
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class InventarioModel(BaseModel):
    """Modelo para la tabla insumos_inventario"""

    def get_table_name(self) -> str:
        return 'insumos_inventario'

    def find_by_insumo(self, id_insumo: str, solo_disponibles: bool = True) -> Dict:
        """Obtener todos los lotes de un insumo"""
        try:
            query = (self.db.table(self.table_name)
                    .select('*, insumos_catalogo(nombre, unidad_medida, categoria)')
                    .eq('id_insumo', id_insumo))

            if solo_disponibles:
                query = query.in_('estado', ['disponible', 'reservado'])

            result = query.order('f_vencimiento').execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo lotes por insumo: {str(e)}")
            return {'success': False, 'error': str(e)}

    def actualizar_cantidad(self, id_lote: str, nueva_cantidad: float, motivo: str = '') -> Dict:
        """Actualizar cantidad de un lote específico"""
        try:
            # Obtener lote actual
            lote_result = self.find_by_id(id_lote, 'id_lote')
            if not lote_result['success']:
                return lote_result

            lote_actual = lote_result['data']

            # Validaciones
            if nueva_cantidad > lote_actual['cantidad_inicial']:
                return {'success': False, 'error': 'La cantidad no puede ser mayor a la inicial'}

            if nueva_cantidad < 0:
                return {'success': False, 'error': 'La cantidad no puede ser negativa'}

            # Determinar nuevo estado
            if nueva_cantidad == 0:
                nuevo_estado = 'agotado'
            elif nueva_cantidad == lote_actual['cantidad_inicial']:
                nuevo_estado = 'disponible'
            else:
                nuevo_estado = lote_actual.get('estado', 'disponible')

            # Preparar datos de actualización
            update_data = {
                'cantidad_actual': nueva_cantidad,
                'estado': nuevo_estado
            }

            # Agregar motivo a observaciones si se proporciona
            if motivo:
                observaciones_actuales = lote_actual.get('observaciones', '')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                nueva_observacion = f"[{timestamp}] {motivo}"

                if observaciones_actuales:
                    update_data['observaciones'] = f"{observaciones_actuales} | {nueva_observacion}"
                else:
                    update_data['observaciones'] = nueva_observacion

            # Actualizar
            result = self.update(id_lote, update_data, 'id_lote')

            if result['success']:
                logger.info(f"Cantidad actualizada - Lote: {id_lote}, Nueva cantidad: {nueva_cantidad}")

            return result

        except Exception as e:
            logger.error(f"Error actualizando cantidad: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_por_vencimiento(self, dias_adelante: int = 7) -> Dict:
        """Obtener lotes que vencen en X días"""
        try:
            fecha_limite = (date.today() + timedelta(days=dias_adelante)).isoformat()
            fecha_hoy = date.today().isoformat()

            result = (self.db.table(self.table_name)
                     .select('*, insumos_catalogo(nombre, es_critico)')
                     .gte('f_vencimiento', fecha_hoy)
                     .lte('f_vencimiento', fecha_limite)
                     .eq('estado', 'disponible')
                     .order('f_vencimiento')
                     .execute())

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo por vencimiento: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_stock_consolidado(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtener stock consolidado por insumo usando la vista"""
        try:
            query = self.db.table('vista_stock_actual').select('*')

            if filtros:
                for key, value in filtros.items():
                    if value is not None:
                        query = query.eq(key, value)

            result = query.order('nombre').execute()

            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error obteniendo stock consolidado: {str(e)}")
            return {'success': False, 'error': str(e)}
