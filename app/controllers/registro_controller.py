from app.models.registro import RegistroModel

class RegistroController:
    
    def __init__(self):
        self.model = RegistroModel()

    def crear_registro(self, usuario, categoria, accion, detalle):
        try:
            registro_data = {
                'usuario_nombre': f"{usuario.nombre} {usuario.apellido}",
                'usuario_rol': usuario.roles[0] if hasattr(usuario, 'roles') and usuario.roles else 'Sin rol',
                'categoria': categoria,
                'accion': accion,
                'detalle': detalle
            }
            self.model.create(registro_data)
        except Exception as e:
            # En un sistema real, aquí se registraría el error en un log.
            print(f"Error al crear registro: {e}")

    def obtener_registros_por_categoria(self, categoria):
        result = self.model.find_by_categoria(categoria)
        return result.get('data', [])

    def obtener_todos_los_registros(self):
        result = self.model.find_all_ordered_by_date()
        return result.get('data', [])
