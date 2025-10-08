from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from datetime import datetime
from app.schemas.roles_schema import RoleSchema

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

    # Usamos role_id en lugar de rol
    role_id = fields.Int(required=True, validate=validate.Range(min=1), load_only=True)
    roles = fields.Nested(RoleSchema, dump_only=True)

    activo = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    legajo = fields.Str(required=True)
    cuil_cuit = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r'^\d{11}$',
            error='El CUIL/CUIT debe contener exactamente 11 dígitos numéricos.'
        )
    )
    telefono = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r'^\+?\d{9,15}$',
            error='El teléfono debe tener un formato internacional (ej: +541122334455) y entre 9 y 15 dígitos.'
        )
    )
    direccion = fields.Str(allow_none=True)
    fecha_nacimiento = fields.Date(allow_none=True)
    fecha_ingreso = fields.Date(allow_none=True)
    supervisor_id = fields.Int(allow_none=True)
    turno = fields.Str(allow_none=True, validate=validate.OneOf(['MAÑANA', 'TARDE', 'NOCHE', 'ROTATIVO']))
    ultimo_login_web = fields.DateTime(dump_only=True, allow_none=True)
    facial_encoding = fields.String(allow_none=True, dump_only=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        """Valida que las fechas sean lógicas"""
        if (data.get('fecha_nacimiento') and data.get('fecha_ingreso') and 
            data['fecha_nacimiento'] > data['fecha_ingreso']):
            raise ValidationError('La fecha de nacimiento no puede ser posterior a la fecha de ingreso')