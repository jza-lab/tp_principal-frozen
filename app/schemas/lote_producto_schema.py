# app/schemas/lote_producto_schema.py
from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from datetime import datetime, date

class LoteProductoSchema(Schema):
    id_lote = fields.Int(dump_only=True)
    producto_id = fields.Int(required=True)
    numero_lote = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    cantidad_inicial = fields.Float(
        required=True,
        validate=validate.Range(min=0.001, max=1000000000, error="La cantidad debe ser un número positivo y no exceder 1,000,000,000.")
    )
    cantidad_actual = fields.Float(
        required=True,
        validate=validate.Range(min=0, max=1000000000, error="La cantidad debe ser un número no negativo y no exceder 1,000,000,000.")
    )
    fecha_produccion = fields.Str(required=True)  # Manejar como string
    fecha_vencimiento = fields.Str(allow_none=True)  # Manejar como string
    costo_produccion_unitario = fields.Float(
        validate=validate.Range(min=0, max=99999999.99, error="El costo debe ser un número no negativo y no exceder 99,999,999.99."),
        allow_none=True
    )
    estado = fields.Str(validate=validate.OneOf(['DISPONIBLE', 'RESERVADO', 'AGOTADO', 'VENCIDO', 'RETIRADO', 'CUARENTENA', 'RECHAZADO']))
    motivo_cuarentena = fields.Str(allow_none=True, validate=validate.Length(max=255))
    cantidad_en_cuarentena = fields.Float(allow_none=True, validate=validate.Range(min=0))
    cantidad_desperdiciada = fields.Float(
        allow_none=True,
        validate=validate.Range(min=0),
        dump_default=0
    )
    ubicacion_fisica = fields.Str(allow_none=True, validate=validate.Length(max=100))
    orden_produccion_id = fields.Int(allow_none=True)
    pedido_id = fields.Int(allow_none=True)
    observaciones = fields.Str(allow_none=True)
    created_at = fields.Str(dump_only=True)  # Manejar como string
    updated_at = fields.Str(dump_only=True)  # Manejar como string
    en_alerta = fields.Boolean(dump_default=False)

    @validates_schema
    def validate_fechas(self, data, **kwargs):
        # Validar fecha_produccion
        fecha_produccion_str = data.get('fecha_produccion')
        if fecha_produccion_str:
            try:
                fecha_produccion = datetime.strptime(fecha_produccion_str, '%Y-%m-%d').date()
                # Validar que no sea futura
                if fecha_produccion > date.today():
                    raise ValidationError('La fecha de producción no puede ser futura')
            except ValueError:
                raise ValidationError({'fecha_produccion': 'Formato de fecha inválido. Use YYYY-MM-DD'})

        # Validar fecha_vencimiento
        fecha_vencimiento_str = data.get('fecha_vencimiento')
        if fecha_vencimiento_str:
            try:
                fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()

                # Si tenemos fecha_produccion, validar que vencimiento no sea anterior
                if fecha_produccion_str:
                    fecha_produccion = datetime.strptime(fecha_produccion_str, '%Y-%m-%d').date()
                    if fecha_vencimiento < fecha_produccion:
                        raise ValidationError('La fecha de vencimiento no puede ser anterior a la fecha de producción')
            except ValueError:
                raise ValidationError({'fecha_vencimiento': 'Formato de fecha inválido. Use YYYY-MM-DD'})

    @validates_schema
    def validate_cantidades(self, data, **kwargs):
        if (data.get('cantidad_inicial') and data.get('cantidad_actual') and
            data['cantidad_actual'] > data['cantidad_inicial']):
            raise ValidationError('La cantidad actual no puede ser mayor que la cantidad inicial')