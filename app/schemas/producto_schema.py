from marshmallow import Schema, fields, validate

class ProductoSchema(Schema):
    """
    Schema para la validación de datos de productos del catálogo.
    """
    # Corregido: Mapear el campo 'id' del schema al atributo 'id' del modelo.
    id = fields.Int(attribute="id")
    # El código ahora es opcional en la carga, ya que se puede autogenerar.
    codigo = fields.Str(required=False, allow_none=True)
    nombre = fields.Str(required=True, validate=validate.Length(min=1, error="El nombre es obligatorio."))
    descripcion = fields.Str(allow_none=True)
    categoria = fields.Str(required=True, validate=validate.Length(min=1, error="La categoría es obligatoria."))
    activo = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    unidad_medida = fields.Str(required=True)
    
    precio_unitario = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.01, error="El precio debe ser mayor que 0."),
        error_messages={"required": "El precio es obligatorio."}
    )

    porcentaje_extra = fields.Decimal(
        as_string=True,
        required=False,
        load_default='0.0'
    )
    
    iva = fields.Bool(
        required=True,
    )