# tp_principal-frozen/app/models/configuracion.py
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class ConfiguracionModel(BaseModel):
    """Modelo para la tabla de configuración"""

    def get_table_name(self) -> str:
        return 'configuracion'

    def obtener_valor(self, clave: str, default=None):
            """Obtiene el valor de una clave de configuración."""
            try:
                # === CORRECCIÓN FINAL: Usar .filter() de la manera más explicita ===
                result = (self.db.table(self.get_table_name())
                        .select('valor')
                        .filter('clave', 'eq', clave)  # <--- Usando .filter()
                        .execute())
                # =================================================================
                
                if result.data:
                    return result.data[0]['valor']
                return default
            except Exception as e:
                # ... (código del logger)
                return default
            
    def guardar_valor(self, clave: str, valor):
        """Guarda o actualiza el valor de una clave de configuración."""
        try:
            # Upsert usa la clave primaria, que es 'clave', y no debería causar el error.
            self.db.table(self.get_table_name()).upsert({'clave': clave, 'valor': valor}).execute()
            return {'success': True}
        except Exception as e:
            logger.error(f"Error guardando configuración '{clave}': {str(e)}")
            return {'success': False, 'error': str(e)}