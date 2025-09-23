from marshmallow import Schema, fields, validate, post_load, ValidationError

class InsumosCatalogoSchema(Schema):
    """Esquema para validación de insumos del catálogo"""

    id_insumo = fields.UUID(dump_only=True)
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
        validate=validate.Range(min=0),
        load_default=None
    )
    stock_max = fields.Int(
        validate=validate.Range(min=0),
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
    # ✅ CAMBIADO: De DateTime a String
    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)

    @post_load
    def validate_stock_max(self, data, **kwargs):
        """Validar que stock_max sea mayor que stock_min"""
        if data.get('stock_max') and data.get('stock_min', 0) >= data['stock_max']:
            raise ValidationError('El stock máximo debe ser mayor al mínimo')
        return data