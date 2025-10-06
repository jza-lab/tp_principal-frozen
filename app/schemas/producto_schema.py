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
    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)
    unidad_medida = fields.Str(dump_only=True)
    precio_unitario = fields.Float(validate=validate.Range(min=1.00, error="El precio unitario debe ser mayor que 0."),
        error_messages={
            "required": "El precio unitario es obligatorio",
            "invalid": "El precio unitario debe ser un número válido."
        },
        allow_none=False,
        load_default=1)