from app.models.base_model import BaseModel
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClienteModel(BaseModel):
    """Modelo para la tabla clientes"""

    def get_table_name(self) -> str:
        return 'clientes'

    def contar_clientes_direccion(self,direccion_id: int) -> int:
        """
        Cuenta el número de clientes que tienen asignada una dirección específica.
        """
        try:
            # Usamos el método select con .count() para obtener solo el recuento.
            # 'exact' asegura que el número total de filas es devuelto en la cabecera.
            response = self.db.table(self.get_table_name()) \
                .select('id', count='exact') \
                .eq('direccion_id', direccion_id) \
                .execute()

            return response.count if response.count is not None else 0

        except Exception as e:
            logger.error(f"Error contando clientes por direccion_id {direccion_id}: {e}")
            # En caso de error, retornamos 0 para evitar fallos.
            return 0

    def get_all(self, filtros: Optional[Dict] = None) -> Dict:
        """Obtener todos los clientes, con filtros opcionales de búsqueda y activos."""
        try:
            query = self.db.table(self.get_table_name()).select("*, direccion:direccion_id(*)")
            
            filtros_copy = filtros.copy() if filtros else {}
            texto_busqueda = filtros_copy.pop('busqueda', None)

            # Lógica de búsqueda avanzada (para el filtro de servidor si se usa)
            if texto_busqueda:
                busqueda_pattern = f"%{texto_busqueda}%"
                # Buscar en nombre, codigo, o cuit (ilike)
                query = query.or_(f"nombre.ilike.{busqueda_pattern},codigo.ilike.{busqueda_pattern},cuit.ilike.{busqueda_pattern}")
            
            # Aplicar filtros restantes (e.g., 'activo')
            for key, value in filtros_copy.items():
                if value is not None:
                    query = query.eq(key, value)

            # Ordenar por activo descendente por defecto
            response = query.order('activo', desc=True).execute() 
            
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_activos(self, include_direccion: bool = False) -> Dict:
        """Obtener todos los clientes activos, opcionalmente con su dirección."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name()).select(query).eq("activo", True).execute()
            return {'success': True, 'data': response.data}
        except Exception as e:
            logger.error(f"Error obteniendo clientes activos: {e}")
            return {'success': False, 'error': str(e)}

    def find_by_id(self, cliente_id: int, include_direccion: bool = False) -> Dict:
        """Busca un cliente por su ID, opcionalmente incluyendo la dirección."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name()).select(query).eq('id', cliente_id).single().execute()
            
            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': False, 'error': 'Cliente no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando cliente por ID {cliente_id}: {e}")
            return {'success': False, 'error': str(e)}

    def buscar_por_email(self, email: str,  include_direccion: bool = False) -> tuple:
        """Busca un cliente por su email."""
        try:
            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name())\
                           .select(query)\
                           .eq("email", email.strip().lower())\
                           .execute()
            
            if len(response.data)>=1:    
                return {'success': True, 'data': response.data}

            return {'success': False, 'error': 'Cliente no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando cliente por email {email}: {e}")
            return {'success': False, 'error': 'Ocurrió un error inesperado al buscar el cliente.'}


    def buscar_por_cuit(self, cuit: str, include_direccion: bool = False) -> Dict:
        """Buscar cliente por CUIT/CUIL"""
        try:

            query = "*, direccion:direccion_id(*)" if include_direccion else "*"
            response = self.db.table(self.get_table_name())\
                           .select(query)\
                           .eq("cuit", cuit.strip())\
                           .execute()
            if response.data:
                return {'success': True, 'data': response.data}
            return {'success': False, 'error': 'Cliente no encontrado'}
        except Exception as e:
            logger.error(f"Error buscando cliente por CUIT {cuit}: {e}")
            return {'success': False, 'error': 'Ocurrió un error inesperado al buscar el cliente.'}