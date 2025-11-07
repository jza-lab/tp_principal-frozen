from app.models.registro import RegistroModel

class RegistroController:
    
    def __init__(self):
        self.model = RegistroModel()

    def crear_registro(self, usuario, categoria, accion, detalle):
        """
        Crea un registro de auditoría.
        Es robusto y maneja diferentes tipos de objetos de usuario.
        La fecha es manejada automáticamente por la base de datos para evitar problemas de zona horaria.
        """
        try:
            usuario_nombre = "Sistema"
            usuario_rol = "N/A"

            if usuario:
                # Intenta obtener nombre y apellido de forma segura
                nombre = getattr(usuario, 'nombre', '')
                apellido = getattr(usuario, 'apellido', '')
                usuario_nombre = f"{nombre} {apellido}".strip()

                # Lógica robusta para obtener el rol
                if hasattr(usuario, 'roles') and usuario.roles:
                    if isinstance(usuario.roles, list):
                        # Caso para SimpleNamespace con lista: ['ROL']
                        usuario_rol = usuario.roles[0]
                    elif isinstance(usuario.roles, dict):
                        # Caso para current_user con diccionario: {'codigo': 'ROL'}
                        usuario_rol = usuario.roles.get('codigo', 'Sin rol')
                elif hasattr(usuario, 'rol') and usuario.rol:
                    # Fallback para current_user si tiene el atributo 'rol' directamente
                    usuario_rol = usuario.rol
            
            registro_data = {
                'usuario_nombre': usuario_nombre,
                'usuario_rol': usuario_rol,
                'categoria': categoria,
                'accion': accion,
                'detalle': detalle
            }
            self.model.create(registro_data)
        except Exception as e:
            # En un sistema real, aquí se registraría el error en un log más persistente.
            print(f"Error al crear registro de auditoría: {e}")

    def obtener_registros_por_categoria(self, categoria):
        result = self.model.find_by_categoria(categoria)
        return result.get('data', [])

    def obtener_todos_los_registros(self):
        result = self.model.find_all_ordered_by_date()
        return result.get('data', [])
