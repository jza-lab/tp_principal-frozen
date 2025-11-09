from dataclasses import dataclass, asdict
from typing import Optional, Dict
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

@dataclass
class Direccion:
    """
    Dataclass que representa una dirección.
    """
    id: Optional[int] = None
    calle: Optional[str] = None
    altura: Optional[int] = None
    piso: Optional[str] = None
    depto: Optional[str] = None
    codigo_postal: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

    def to_dict(self):
        return asdict(self)

class DireccionModel(BaseModel):
    """
    Modelo para interactuar con la tabla de direcciones.
    """
    def get_table_name(self) -> str:
        return 'usuario_direccion'

    def create(self, data: Dict) -> Dict:
        """
        Crea un nuevo registro de dirección en la base de datos.
        """
        try:
            # Asegurarse de que no haya valores None que puedan causar problemas
            direccion_data = {k: v for k, v in data.items() if v is not None and v != 'None'}

            response = self.db.table(self.get_table_name()).insert(direccion_data).execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                # Esto podría ocurrir si la inserción falla silenciosamente o por RLS
                return {'success': False, 'error': 'No se pudo crear la dirección.'}

        except Exception as e:
            logger.error(f"Error creando dirección: {e}")
            # Manejar violación de unicidad
            if 'uq_direccion_completa' in str(e):
                return {'success': False, 'error': 'La dirección ya existe.', 'code': 'duplicate'}
            return {'success': False, 'error': str(e)}

    def find_by_id(self, direccion_id: int) -> Dict:
        """
        Busca una dirección por su ID.
        """
        return self._find_by('id', direccion_id)

    def find_by_full_address(self, calle: str, altura: int, piso: Optional[str], depto: Optional[str], localidad: str, provincia: str) -> Dict:
        """
        Busca una dirección exacta para evitar duplicados.
        Maneja correctamente los campos opcionales (piso, depto) que pueden ser NULL o strings vacíos.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*')
            query = query.eq('calle', calle)
            query = query.eq('altura', altura)
            query = query.eq('localidad', localidad)
            query = query.eq('provincia', provincia)

            # Si 'piso' tiene un valor, se busca ese valor.
            # Si no, se busca donde 'piso' es NULL o es un string vacío.
            if piso:
                query = query.eq('piso', piso)
            else:
                query = query.or_("piso.is.null,piso.eq.''")

            # Si 'depto' tiene un valor, se busca ese valor.
            # Si no, se busca donde 'depto' es NULL o es un string vacío.
            if depto:
                query = query.eq('depto', depto)
            else:
                query = query.or_("depto.is.null,depto.eq.''")

            result = query.execute()

            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'Dirección no encontrada'}

        except Exception as e:
            logger.error(f"Error buscando dirección completa: {str(e)}")
            return {'success': False, 'error': str(e)}


    def _find_by(self, field: str, value) -> Dict:
        """
        Método genérico y privado para buscar una dirección por un campo específico.
        """
        try:
            query = self.db.table(self.get_table_name()).select('*').eq(field, value)
            result = query.execute()
            
            if not result.data:
                return {'success': False, 'error': 'Dirección no encontrada'}

            return {'success': True, 'data': result.data[0]}
            
        except Exception as e:
            logger.error(f"Error buscando dirección por {field}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update(self, direccion_id: int, data: Dict) -> Dict:
        """
        Actualiza un registro de dirección existente en la base de datos.
        """
        try:
            # Limpiar datos nulos para evitar sobrescribir campos con None accidentalmente
            update_data = {k: v for k, v in data.items() if v is not None}

            response = self.db.table(self.get_table_name()).update(update_data).eq("id", direccion_id).execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            else:
                return {'success': False, 'error': 'No se encontró la dirección para actualizar.'}

        except Exception as e:
            logger.error(f"Error actualizando dirección ID {direccion_id}: {e}")
            return {'success': False, 'error': str(e)}

    def is_address_shared(self, direccion_id: int, excluding_user_id: int) -> bool:
        """
        Verifica si una dirección está siendo utilizada por más de una entidad,
        excluyendo al usuario actual para evitar falsos positivos.
        """
        from app.models.usuario import UsuarioModel
        from app.models.cliente import ClienteModel
        from app.models.proveedor import ProveedorModel

        user_model = UsuarioModel()
        client_model = ClienteModel()
        provider_model = ProveedorModel()

        try:
            # 1. Contar usuarios en esta dirección, excluyendo al actual
            # La API de Supabase no permite un "count" con filtro "not.eq" directo,
            # así que contamos todos y restamos si el usuario actual está ahí.
            all_users_count = user_model.contar_usuarios_direccion(direccion_id)
            
            # Verificamos si el usuario a excluir VIVE en esa dirección.
            user_to_exclude_res = user_model.find_by_id(excluding_user_id)
            user_lives_here = (user_to_exclude_res.get('success') and 
                               user_to_exclude_res['data'].get('direccion_id') == direccion_id)

            user_count = all_users_count
            if user_lives_here:
                user_count -= 1

            # 2. Contar clientes y proveedores
            client_count = client_model.contar_clientes_direccion(direccion_id)
            provider_count = provider_model.contar_proveedores_direccion(direccion_id)
            
            total_shares = user_count + client_count + provider_count
            
            return total_shares > 0

        except Exception as e:
            logger.error(f"Error verificando si la dirección {direccion_id} es compartida: {e}")
            # En caso de error, asumimos que es compartida para ser cautelosos
            return True

    def search_distinct_localidades(self, term: str):
        """
        Busca localidades únicas que coincidan parcialmente con un término de búsqueda.
        La búsqueda no distingue entre mayúsculas y minúsculas.
        Devuelve una lista de diccionarios con id, localidad y provincia.
        """
        try:
            # Seleccionamos los campos necesarios y filtramos
            response = self.db.table(self.get_table_name()).select('id, localidad, provincia').ilike('localidad', f'%{term}%').limit(20).execute()

            if not response.data:
                return {'success': True, 'data': []}

            # Procesamos para obtener localidades únicas (combinación de localidad y provincia)
            localidades_vistas = set()
            localidades_unicas = []
            for item in response.data:
                # Clave única para la combinación de localidad y provincia
                clave_localidad = (item['localidad'].strip().lower(), item['provincia'].strip().lower())
                if clave_localidad not in localidades_vistas:
                    localidades_vistas.add(clave_localidad)
                    localidades_unicas.append({
                        'id': item['id'], # Usamos el ID de la primera dirección encontrada para esta localidad
                        'localidad': item['localidad'],
                        'provincia': item['provincia']
                    })
            
            return {'success': True, 'data': localidades_unicas}

        except Exception as e:
            logger.error(f"Error buscando localidades: {e}")
            return {'success': False, 'error': str(e), 'data': []}