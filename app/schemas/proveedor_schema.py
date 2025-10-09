from marshmallow import Schema, fields, validate

class ProveedorSchema(Schema):
    """Esquema para validación de proveedores"""

    id = fields.Int(dump_only=True)
    codigo = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
        error_messages={'required': 'El código es obligatorio'}
    )
    nombre = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={'required': 'El nombre es obligatorio'}
    )
    contacto = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    telefono = fields.Str(
        validate=validate.Length(max=20),
        allow_none=True,
        load_default=None
    )
    email = fields.Email(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    direccion = fields.Str(allow_none=True, load_default=None)
    cuit = fields.Str(
        validate=validate.Length(max=15),
        allow_none=True,
        load_default=None
    )
    condicion_iva = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        load_default=None
    )
    activo = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)