from marshmallow import Schema, fields, validate

class ProductoSchema(Schema):
    """
    Schema para la validación de datos de productos del catálogo.
    """
    id = fields.Int(dump_only=True)
    # El código ahora es opcional en la carga, ya que se puede autogenerar.
    codigo = fields.Str(required=False, allow_none=True)
    nombre = fields.Str(required=True, validate=validate.Length(min=1, error="El nombre es obligatorio."))
    descripcion = fields.Str(allow_none=True)
    categoria = fields.Str(required=True, validate=validate.Length(min=1, error="La categoría es obligatoria."))
    activo = fields.Bool(dump_only=True)
    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)
    unidad_medida = fields.Str(required=True)
    unidades_por_paquete = fields.Int(
        required=False,
        allow_none=True,
        load_default=1
    )
    peso_por_paquete_valor = fields.Float(
        required=False,
        allow_none=True,
        load_default=0
    )

    cantidad_maxima_x_pedido = fields.Int(
        required=False,
        allow_none=True,
        load_default=0,
        validate=validate.Range(min=0, error="La cantidad máxima no puede ser negativa.")
    )

    peso_por_paquete_unidad = fields.Str(
        required=False,
        allow_none=True,
        load_default=''
    )
    
    precio_unitario = fields.Float(
        required=True,
        validate=validate.Range(min=0.01, error="El precio debe ser mayor que 0."),
        error_messages={"required": "El precio es obligatorio."}
    )

    porcentaje_extra = fields.Float(
        required=False)
    
    iva = fields.Bool(
        required=True)
    
    stock_min_produccion = fields.Int(
        required=False,
        allow_none=True,
        load_default=0,
        validate=validate.Range(min=0, error="El stock mínimo no puede ser negativo.")
    )