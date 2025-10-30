from marshmallow import Schema, fields, validate, post_load, ValidationError, validates_schema
from datetime import date

class InsumosInventarioSchema(Schema):
    """Esquema para validación de inventario"""

    id_lote = fields.UUID(dump_only=True)
    id_insumo = fields.UUID(required=True, error_messages={'required': 'El ID del insumo es obligatorio'})
    id_proveedor = fields.Int(allow_none=True)
    usuario_ingreso_id = fields.Int(allow_none=True)

    numero_lote_proveedor = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True
    )
    cantidad_inicial = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.001, error="La cantidad inicial debe ser un valor mayor a 0."),
        error_messages={
            "required": "La cantidad inicial es obligatoria.",
            "invalid": "La cantidad debe ser un número válido."
        }
    )
    cantidad_actual = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0, error="La cantidad actual no puede ser negativa."),
        error_messages={
            "required": "La cantidad actual es obligatoria.",
            "invalid": "La cantidad debe ser un número válido."
        }
    )
    precio_unitario = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        allow_none=True
    )
    costo_total = fields.Decimal(as_string=True, dump_only=True)

    f_ingreso = fields.Date(load_default=date.today)
    f_vencimiento = fields.Date(allow_none=True)

    ubicacion_fisica = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True
    )
    documento_ingreso = fields.Str(
        validate=validate.Length(max=255),
        allow_none=True
    )
    observaciones = fields.Str(allow_none=True)

    estado = fields.Str(validate=validate.OneOf([
        'disponible', 'agotado', 'reservado', 'vencido', 'retirado', 'cuarentena'
    ]), dump_default='disponible')

    # 2. Añadir los nuevos campos
    motivo_cuarentena = fields.Str(allow_none=True)
    cantidad_en_cuarentena = fields.Float(allow_none=True, dump_default=0)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_fechas(self, data, **kwargs):
        """Validar que la fecha de vencimiento sea posterior a la de ingreso."""
        if data.get('f_vencimiento') and data.get('f_ingreso'):
            if data['f_vencimiento'] < data['f_ingreso']:
                raise ValidationError('La fecha de vencimiento no puede ser anterior a la fecha de ingreso.', 'f_vencimiento')
        return data

    @validates_schema
    def validate_cantidades(self, data, **kwargs):
        """Validar que cantidad_actual no sea mayor que cantidad_inicial"""
        # Se valida solo si ambos campos están presentes
        if 'cantidad_actual' in data and 'cantidad_inicial' in data:
            if data['cantidad_actual'] > data['cantidad_inicial']:
                raise ValidationError('La cantidad actual no puede ser mayor que la inicial.', 'cantidad_actual')
        return data

    @post_load
    def set_defaults(self, data, **kwargs):
        """Establecer valores por defecto post-carga."""
        # Si cantidad_actual no se provee, se iguala a cantidad_inicial
        if 'cantidad_inicial' in data and 'cantidad_actual' not in data:
            data['cantidad_actual'] = data['cantidad_inicial']
        return data