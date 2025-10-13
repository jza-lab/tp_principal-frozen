from app.database import Database
from datetime import datetime
from typing import Dict, List
import logging

class HistorialPreciosController:
    def __init__(self):
        self.db = Database().client
        logger = logging.getLogger(__name__)
        self.table = 'historial_precios_insumos'

    def registrar_cambio(self, datos: Dict) -> Dict: # Cambiado a -> Dict
        """
        Registra un cambio de precio en el historial y devuelve un diccionario de resultado.
        """
        try:
            datos_completos = {
                **datos,
                'fecha_cambio': datetime.now().isoformat()
            }

            response = self.db.table(self.table)\
                           .insert(datos_completos)\
                           .execute()

            # --- CORRECCIÓN ---
            # Verificamos si la inserción devolvió datos y devolvemos un diccionario estándar.
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No se pudo registrar el cambio en el historial.'}
            # ------------------

        except Exception as e:
            logging.error(f"Error registrando cambio de precio: {str(e)}")
            return {'success': False, 'error': str(e)} # Devolvemos un diccionario de error

    def obtener_historial_insumo(self, id_insumo: str) -> List[Dict]:
        """
        Obtiene el historial de precios de un insumo
        """
        try:
            response = self.db.table(self.table)\
                           .select('*')\
                           .eq('id_insumo', id_insumo)\
                           .order('fecha_cambio', desc=True)\
                           .execute()

            return response.data if response.data else []

        except Exception as e:
            logging.error(f"Error obteniendo historial insumo {id_insumo}: {str(e)}")
            return []