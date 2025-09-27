from marshmallow import Schema, fields, validate

class UsuarioSchema(Schema):
    """
    Schema para la validación de datos de usuarios.
    """
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    nombre = fields.Str(required=True, validate=validate.Length(min=1))
    apellido = fields.Str(required=True, validate=validate.Length(min=1))

    # El password solo se usa para crear o actualizar, no para mostrar.
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))

    # Validar que el rol sea uno de los predefinidos
    rol = fields.Str(required=True, validate=validate.OneOf(
        ['ADMIN', 'GERENTE', 'SUPERVISOR', 'OPERARIO', 'VENTAS']
    ))

    activo = fields.Bool(dump_only=True)
    creado_en = fields.DateTime(dump_only=True)
    actualizado_en = fields.DateTime(dump_only=True)
    numero_empleado = fields.Str(allow_none=True)
    dni = fields.Str(allow_none=True)
    telefono = fields.Str(allow_none=True)
    direccion = fields.Str(allow_none=True)
    fecha_nacimiento = fields.Date(allow_none=True)
    fecha_ingreso = fields.Date(allow_none=True)
    departamento = fields.Str(allow_none=True)
    puesto = fields.Str(allow_none=True)
    supervisor_id = fields.Int(allow_none=True)
    turno = fields.Str(allow_none=True)
    ultimo_login = fields.DateTime(dump_only=True, allow_none=True)
    login_totem_activo = fields.Boolean(allow_none=True)
    ultimo_login_totem = fields.DateTime(allow_none=True)
    totem_session_id = fields.String(allow_none=True)
    ultimo_login_web = fields.DateTime(allow_none=True)