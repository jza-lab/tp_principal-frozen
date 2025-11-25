from .base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class PagoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de pagos.
    """
    def __init__(self):
        super().__init__()

    def get_table_name(self) -> str:
        return "pagos"

    def get_pagos_by_pedido_id(self, id_pedido: int) -> dict:
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, usuario_registro:id_usuario_registro(nombre)"
            ).eq("id_pedido", id_pedido).order("created_at", desc=True)
            
            result = query.execute()
            return {'success': True, 'data': result.data}

        except Exception as e:
            logger.error(f"Error al obtener pagos para el pedido {id_pedido}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_by_id(self, id_pago: int) -> dict:
        try:
            query = self.db.table(self.get_table_name()).select("*").eq("id_pago", id_pago).maybe_single()
            result = query.execute()
            
            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': False, 'error': "Pago no encontrado."}
        except Exception as e:
            logger.error(f"Error al buscar pago por ID {id_pago}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_pagos_en_rango(self, fecha_inicio, fecha_fin) -> dict:
        """
        Obtiene todos los pagos verificados registrados dentro del rango de fechas especificado.
        Utiliza 'created_at' como fecha de referencia del flujo de caja.
        """
        try:
            # Se asume que created_at es la fecha efectiva del ingreso del dinero
            query = self.db.table(self.get_table_name()).select('*')\
                .gte('created_at', fecha_inicio.isoformat())\
                .lte('created_at', fecha_fin.isoformat())\
                .eq('estado', 'verificado')
            
            result = query.execute()
            return {'success': True, 'data': result.data}
        except Exception as e:
            logger.error(f"Error obteniendo pagos en rango {fecha_inicio} - {fecha_fin}: {e}")
            return {'success': False, 'error': str(e)}