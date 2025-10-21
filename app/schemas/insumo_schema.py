from marshmallow import Schema, fields, post_load, validate, validates_schema, ValidationError

from app.schemas.proveedor_schema import ProveedorSchema

class InsumosCatalogoSchema(Schema):
    """Esquema para validación de insumos del catálogo"""

    id_insumo = fields.UUID(dump_only=True)
    id = fields.Str(attribute="id_insumo", dump_only=True)
    nombre = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={'required': 'El nombre es obligatorio'}
    )
    codigo_interno = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        load_default=None
    )
    stock_actual = fields.Float(
        allow_none=True,
        load_default=None
    )
    codigo_ean = fields.Str(
        validate=validate.Length(max=13),
        allow_none=True,
        load_default=None
    )
    unidad_medida = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=20),
        error_messages={'required': 'La unidad de medida es obligatoria'}
    )
    categoria = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    descripcion = fields.Str(allow_none=True, load_default=None)
    tem_recomendada = fields.Float(allow_none=True, load_default=None)

    stock_min = fields.Int(
        validate=validate.Range(min=0, error="El stock mínimo no puede ser negativo."),
        error_messages={
            "required": "El stock mínimo es obligatorio",
            "invalid": "El stock mínimo debe ser un número válido."
        },
        allow_none=True,
        load_default=None
    )
    stock_max = fields.Int(
        validate=validate.Range(min=0, error="El stock máximo no puede ser negativo."),
        error_messages={
            "required": "El stock máximo es obligatorio",
            "invalid": "El stock máximo debe ser un número válido."
        },
        allow_none=True,
        load_default=None
    )

    vida_util_dias = fields.Int(
        validate=validate.Range(min=1),
        allow_none=True,
        load_default=None
    )
    es_critico = fields.Bool(load_default=None)
    requiere_certificacion = fields.Bool(load_default=None)
    activo = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    precio_unitario = fields.Float(
        validate=validate.Range(min=1.00, error="El precio unitario debe ser mayor que 0."),
        error_messages={
            "required": "El precio unitario es obligatorio",
            "invalid": "El precio unitario debe ser un número válido."
        },
        allow_none=False,
        load_default=1
    )
    id_proveedor = fields.Int(
        allow_none=True,
        load_default=None
    )
    proveedor = fields.Nested(ProveedorSchema, allow_none=True)
    tiempo_entrega_dias = fields.Int(allow_none=True)

    @post_load
    def validate_stock_max(self, data, **kwargs):
        """Validar que stock_max sea mayor que stock_min"""
        if data.get('stock_max') is not None and data.get('stock_min') is not None:
            if data['stock_min'] >= data['stock_max']:
                raise ValidationError("El stock máximo debe ser mayor que el mínimo")
        return data