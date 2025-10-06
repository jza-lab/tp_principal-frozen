from marshmallow import Schema, fields, validate

class RoleSchema(Schema):
    """
    Schema para la validación de datos de roles.
    """
    id = fields.Int(dump_only=True)
    codigo = fields.Str(required=True, validate=validate.Length(min=1))
    nombre = fields.Str(required=True, validate=validate.Length(min=1))
    nivel = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    descripcion = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)