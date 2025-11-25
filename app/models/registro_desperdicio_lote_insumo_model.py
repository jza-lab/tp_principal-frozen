# app/models/registro_desperdicio_lote_insumo_model.py
from app.models.base_model import BaseModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RegistroDesperdicioLoteInsumoModel(BaseModel):
    def get_table_name(self) -> str:
        return 'registros_desperdicio_lote_insumo'

    def get_schema_name(self) -> str:
        return "mes_kanban"

    def _get_query_builder(self):
        """Sobrescribe el método base para especificar el esquema."""
        return self.db.schema(self.get_schema_name()).table(self.get_table_name())

    def get_by_lote_id(self, lote_insumo_id: int):
        """Obtiene todos los registros de desperdicio para un lote específico."""
        try:
            # Se elimina el join a 'usuarios' que causa el error de cross-schema.
            # El join a 'motivos' funciona porque está en el mismo schema 'mes_kanban'.
            # Nota: Para insumos, la tabla de motivos suele ser 'motivos_desperdicio_lote'
            result = self._get_query_builder().select(
                '*, motivo:motivos_desperdicio_lote(descripcion)'
            ).eq('lote_insumo_id', lote_insumo_id).order('created_at', desc=True).execute()

            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error buscando registros de desperdicio por lote de insumo: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_in_date_range(self, fecha_inicio: datetime, fecha_fin: datetime):
        """Obtiene todos los registros de desperdicio dentro de un rango de fechas."""
        try:
            query = self._get_query_builder().select(
                '*, motivo:motivos_desperdicio_lote(descripcion)'
            )
            query = query.gte('created_at', fecha_inicio.isoformat())
            query = query.lte('created_at', fecha_fin.isoformat())
            result = query.execute()
            
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error buscando registros de desperdicio de insumo por rango de fecha: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_all_by_op_and_insumo(self, orden_id: int, insumo_id: int) -> list:
        """
        Encuentra todos los registros de merma para una OP y un Insumo específicos.
        Realiza un join implícito a través de dos consultas para evitar problemas cross-schema.
        """
        try:
            # 1. Obtener todos los IDs de lote para el insumo dado.
            # Asumimos que la tabla de inventario está en el schema 'public'.
            lotes_res = self.db.table('insumos_inventario').select('id_lote').eq('id_insumo', insumo_id).execute()
            if not lotes_res.data:
                return []

            lote_ids = [lote['id_lote'] for lote in lotes_res.data]

            # 2. Buscar registros de merma que coincidan con la OP y los IDs de lote.
            result = self._get_query_builder().select('*') \
                .eq('orden_produccion_id', orden_id) \
                .in_('lote_insumo_id', lote_ids) \
                .execute()

            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error en find_all_by_op_and_insumo: {str(e)}")
            return []

    def find_all_by_op_id(self, orden_id: int):
        """Obtiene todos los registros de desperdicio para una orden de producción específica."""
        try:
            result = self._get_query_builder().select('*').eq('orden_produccion_id', orden_id).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error en find_all_by_op_id: {str(e)}")
            return []

    def get_enriched_historial_by_op(self, orden_id: int):
        """
        Obtiene un historial enriquecido de mermas de insumos para una OP específica.
        Utiliza consultas separadas para evitar joins cross-schema problemáticos.
        """
        try:
            # 1. Obtener los registros de merma base
            mermas_res = self._get_query_builder().select('*').eq('orden_produccion_id', orden_id).order('created_at', desc=True).execute()
            if not mermas_res.data:
                return {'success': True, 'data': []}
            
            mermas = mermas_res.data
            
            # 2. Recopilar IDs
            lote_ids = {m['lote_insumo_id'] for m in mermas if m.get('lote_insumo_id')}
            motivo_ids = {m['motivo_id'] for m in mermas if m.get('motivo_id')}
            usuario_ids = {m['usuario_id'] for m in mermas if m.get('usuario_id')}

            # 3. Consultas de enriquecimiento
            lotes_data = self.db.table('insumos_inventario').select('id_lote, numero_lote_proveedor, insumo:id_insumo(nombre)').in_('id_lote', list(lote_ids)).execute().data if lote_ids else []
            motivos_data = self.db.schema('mes_kanban').table('motivos_desperdicio').select('id, descripcion').in_('id', list(motivo_ids)).execute().data if motivo_ids else []
            usuarios_data = self.db.table('usuarios').select('id, nombre, apellido').in_('id', list(usuario_ids)).execute().data if usuario_ids else []

            # 4. Mapear datos para búsqueda rápida
            lotes_map = {l['id_lote']: l for l in lotes_data}
            motivos_map = {m['id']: m for m in motivos_data}
            usuarios_map = {u['id']: u for u in usuarios_data}
            
            # 5. Combinar datos
            for merma in mermas:
                merma['lote'] = lotes_map.get(merma.get('lote_insumo_id'))
                merma['motivo'] = motivos_map.get(merma.get('motivo_id'))
                merma['usuario'] = usuarios_map.get(merma.get('usuario_id'))

            return {'success': True, 'data': mermas}
            
        except Exception as e:
            logger.error(f"Error obteniendo historial enriquecido de mermas: {str(e)}")
            return {'success': False, 'error': str(e)}
