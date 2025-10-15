from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app.schemas.roles_schema import RoleSchema
from app.schemas.direccion_schema import DireccionSchema

class UsuarioSchema(Schema):
    """
    Esquema para la validación y serialización de datos de usuarios.
    Este esquema define la estructura de los datos de un usuario, aplicando reglas
    de validación para la entrada (carga) de datos y controlando qué campos
    se exponen en la salida.
    """
    # --- Campos de Identificación y Auditoría (Solo Lectura) ---
    id = fields.Int(dump_only=True, description="Identificador único del usuario.")
    activo = fields.Bool(dump_only=True, description="Indica si el usuario está activo en el sistema.")
    created_at = fields.DateTime(dump_only=True, description="Fecha y hora de creación del registro.")
    updated_at = fields.DateTime(dump_only=True, description="Fecha y hora de la última actualización.")
    ultimo_login_web = fields.DateTime(dump_only=True, allow_none=True, description="Fecha y hora del último inicio de sesión web.")
    facial_encoding = fields.String(allow_none=True, dump_only=True, description="Codificación facial del usuario (si existe).")

    # --- Datos Personales y de Contacto ---
    nombre = fields.Str(
        required=True,
        validate=validate.Length(min=1, error="El nombre no puede estar vacío."),
        description="Nombre del usuario."
    )
    apellido = fields.Str(
        required=True,
        validate=validate.Length(min=1, error="El apellido no puede estar vacío."),
        description="Apellido del usuario."
    )
    email = fields.Email(required=True, description="Correo electrónico del usuario (debe ser único).")
    telefono = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r'^\d{7,15}$',
            error='El teléfono debe contener solo números y tener entre 7 y 15 dígitos.'
        ),
        description="Número de teléfono del usuario."
    )
    fecha_nacimiento = fields.Date(allow_none=True, description="Fecha de nacimiento del usuario.")

    # --- Datos Laborales ---
    legajo = fields.Str(
        required=True,
        validate=validate.Length(min=1, error="El legajo no puede estar vacío."),
        description="Número de legajo del empleado (debe ser único)."
    )
    cuil_cuit = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r'^\d{2}-\d{8}-\d{1}$',
            error='El formato del CUIL/CUIT debe ser XX-XXXXXXXX-X.'
        ),
        description="CUIL/CUIT del usuario."
    )
    fecha_ingreso = fields.Date(allow_none=True, description="Fecha de ingreso del usuario a la empresa.")
    turno_id = fields.Int(allow_none=True, load_default=None, description="ID del turno de trabajo asignado.")

    # --- Campos de Seguridad y Relaciones ---
    
    # El password es de solo escritura (load_only): se acepta para crear/actualizar, pero nunca se muestra.
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, error="La contraseña debe tener al menos 8 caracteres.")
    )

    # El ID del rol se usa para la carga de datos.
    role_id = fields.Int(
        required=True,
        load_only=True,
        validate=validate.Range(min=1, error="El ID de rol no es válido.")
    )
    # El objeto completo del rol se usa para el volcado de datos.
    roles = fields.Nested(RoleSchema, dump_only=True, description="Rol asignado al usuario.")
    
    # El ID de la dirección se usa para la carga de datos.
    direccion_id = fields.Int(allow_none=True, load_only=True)
    # El objeto completo de la dirección se usa para el volcado de datos.
    direccion = fields.Nested(DireccionSchema, dump_only=True, description="Dirección del usuario.")

    @validates_schema
    def validate_dates(self, data, **kwargs):
        """
        Validación a nivel de esquema para asegurar la coherencia entre fechas.
        """
        fecha_nacimiento = data.get('fecha_nacimiento')
        fecha_ingreso = data.get('fecha_ingreso')

        if fecha_nacimiento and fecha_ingreso and fecha_nacimiento >= fecha_ingreso:
            raise ValidationError(
                'La fecha de nacimiento no puede ser igual o posterior a la fecha de ingreso.',
                'fecha_nacimiento'
            )
