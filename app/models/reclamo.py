from app.models.base_model import BaseModel
from datetime import datetime
from typing import Dict

class ReclamoModel(BaseModel):
    """
    Modelo para gestionar los reclamos en la base de datos.
    """
    def get_table_name(self) -> str:
        return 'reclamos'

    def find_by_id_con_mensajes(self, reclamo_id: int) -> Dict:
        """
        Obtiene un reclamo y todos sus mensajes asociados.
        """
        try:
            # 1. Obtener el reclamo principal
            reclamo_resp = self.db.table(self.get_table_name()).select(
                "*, cliente:clientes(nombre, email), pedido:pedidos(id)" # Corregido aquí también (cliente:clientes y pedido:pedidos)
            ).eq('id', reclamo_id).single().execute()
            
            if not reclamo_resp.data:
                return {'success': False, 'error': 'Reclamo no encontrado'}
            
            reclamo = reclamo_resp.data

            # 2. Obtener los mensajes
            # --- SECCIÓN CORREGIDA ---
            select_query_mensajes = """
                *,
                autor_admin:usuarios ( nombre, apellido ),
                autor_cliente:clientes ( nombre )
            """
            # --- FIN SECCIÓN CORREGIDA ---
            
            mensajes_resp = self.db.table('reclamo_mensajes').select(
                select_query_mensajes
            ).eq('reclamo_id', reclamo_id).order('created_at', desc=False).execute()
            
            reclamo['mensajes'] = mensajes_resp.data or []
            
            return {'success': True, 'data': reclamo}

        except Exception as e:
            # Devolvemos el error de la base de datos para depuración
            return {'success': False, 'error': f'Error de base de datos: {str(e)}'}

    def find_all_admin(self) -> Dict:
        """
        Obtiene todos los reclamos para la vista de administrador.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, cliente:clientes(nombre), pedido:pedidos(id)" # Corregido aquí también
            ).order('created_at', desc=True)
            
            response = query.execute()
            return {'success': True, 'data': response.data or []}
        except Exception as e:
            return {'success': False, 'error': f'Error de base de datos: {str(e)}'}

    def update_estado(self, reclamo_id: int, nuevo_estado: str) -> Dict:
            """
            Actualiza el estado de un reclamo.
            """
            try:
                update_data = {
                    'estado': nuevo_estado
                    # 'updated_at': datetime.now().isoformat() # <-- ELIMINA O COMENTA ESTA LÍNEA
                }
                
                return self.update(reclamo_id, update_data, 'id')
            except Exception as e:
                return {'success': False, 'error': str(e)}
            
    def obtener_por_cliente(self, cliente_id: int) -> Dict:
        """
        Obtiene todos los reclamos para un cliente específico.
        """
        try:
            query = self.db.table(self.get_table_name()).select(
                "*, pedido:pedidos(id)" # Corregido aquí también
            ).eq('cliente_id', cliente_id).order('created_at', desc=True)
            
            response = query.execute()
            return {'success': True, 'data': response.data or []}
        except Exception as e:
            return {'success': False, 'error': f'Error de base de datos: {str(e)}'}
        
    def get_count_by_estado(self, estado: str) -> Dict:
        """
        Obtiene la cantidad de reclamos en un estado específico.
        """
        try:
            # Usamos count='exact' para obtener solo el conteo de forma eficiente
            response = self.db.table(self.get_table_name()) \
                                .select('id', count='exact') \
                                .eq('estado', estado) \
                                .execute()
            
            # response.count nos da el número total
            return {'success': True, 'count': response.count}
        
        except Exception as e:
            return {'success': False, 'error': f'Error de base de datos: {str(e)}', 'count': 0}
        
    def get_count_by_cliente_and_estado(self, cliente_id: int, estado: str) -> Dict:
        """
        Obtiene la cantidad de reclamos de un cliente en un estado específico.
        """
        try:
            # Usamos count='exact' para obtener solo el conteo de forma eficiente
            response = self.db.table(self.get_table_name()) \
                             .select('id', count='exact') \
                             .eq('cliente_id', cliente_id) \
                             .eq('estado', estado) \
                             .execute()
            
            # response.count nos da el número total
            return {'success': True, 'count': response.count}
        
        except Exception as e:
            logger.error(f"Error contando reclamos para cliente {cliente_id}: {e}", exc_info=True)
            return {'success': False, 'error': f'Error de base de datos: {str(e)}', 'count': 0}
