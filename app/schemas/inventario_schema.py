from marshmallow import Schema, fields, validate, post_load, ValidationError
from datetime import date

class InsumosInventarioSchema(Schema):
    """Esquema para validación de inventario"""

    id_lote = fields.UUID(dump_only=True)
    id_insumo = fields.UUID(
        required=True,
        error_messages={'required': 'El ID del insumo es obligatorio'}
    )
    id_proveedor = fields.UUID(allow_none=True, load_default=None)
    numero_lote_proveedor = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    cantidad_inicial = fields.Decimal(
        required=True,
        validate=validate.Range(min=0.001),
        places=3,
        error_messages={'required': 'La cantidad inicial es obligatoria'}
    )
    cantidad_actual = fields.Decimal(
        validate=validate.Range(min=0),
        places=3,
        allow_none=True
    )
    precio_unitario = fields.Decimal(
        validate=validate.Range(min=0),
        places=2,
        allow_none=True,
        load_default=None
    )
    costo_total = fields.Decimal(dump_only=True, places=2)
    f_ingreso = fields.Date(allow_none=True)
    f_vencimiento = fields.Date(allow_none=True, load_default=None)
    ubicacion_fisica = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    documento_ingreso = fields.Str(
        validate=validate.Length(max=255),
        allow_none=True,
        load_default=None
    )
    observaciones = fields.Str(allow_none=True, load_default=None)
    usuario_ingreso = fields.UUID(allow_none=True, load_default=None)
    estado = fields.Str(
        validate=validate.OneOf(['disponible', 'reservado', 'agotado', 'vencido']),
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_load
    def validate_fechas(self, data, **kwargs):
        """Validar fechas lógicas"""
        f_ingreso = data.get('f_ingreso')
        f_vencimiento = data.get('f_vencimiento')

        if f_vencimiento and f_ingreso and f_vencimiento < f_ingreso:
            raise ValidationError('La fecha de vencimiento no puede ser anterior al ingreso')

        return data

    @post_load
    def set_defaults(self, data, **kwargs):
        """Establecer valores por defecto"""
        if not data.get('f_ingreso'):
            # ✅ Cambiar a objeto date en lugar de string
            data['f_ingreso'] = date.today()

        if not data.get('cantidad_actual'):
            data['cantidad_actual'] = data['cantidad_inicial']

        return data