from marshmallow import Schema, fields, validate

class ProductoSchema(Schema):
    """
    Schema para la validación de datos de productos del catálogo.
    """
    id = fields.Int(dump_only=True)
    codigo = fields.Str(required=True, validate=validate.Length(min=1))
    nombre = fields.Str(required=True, validate=validate.Length(min=1))
    descripcion = fields.Str(allow_none=True)
    categoria = fields.Str(required=True, validate=validate.Length(min=1))
    activo = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)