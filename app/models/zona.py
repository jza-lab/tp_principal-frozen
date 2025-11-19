from app.models.base_model import BaseModel

class ZonaModel(BaseModel):
    def get_table_name(self):
        return 'zonas'

    def find_by_postal_code(self, codigo_postal):
        """
        Busca una zona cuyo rango de códigos postales incluya el código postal dado.
        """
        try:
            result = self.db.table(self.get_table_name()) \
                .select('*') \
                .lte('codigo_postal_inicio', codigo_postal) \
                .gte('codigo_postal_fin', codigo_postal) \
                .limit(1) \
                .execute()
            
            if result.data:
                return {'success': True, 'data': result.data[0]}
            else:
                return {'success': False, 'error': 'No se encontró una zona para el código postal proporcionado.'}
        except Exception as e:
            return {'success': False, 'error': f'Error en la base de datos: {str(e)}'}

class ZonaLocalidadModel(BaseModel):
    def get_table_name(self):
        return 'zonas_localidades'
