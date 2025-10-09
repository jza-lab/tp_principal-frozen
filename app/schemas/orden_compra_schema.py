from marshmallow import Schema, fields, validate
from datetime import date

class OrdenCompraSchema(Schema):
    id = fields.Int(dump_only=True)
    codigo_oc = fields.Str(dump_only=True)  # Se genera automáticamente
    proveedor_id = fields.Int(required=True)
    pedido_id = fields.Int(allow_none=True)
    orden_produccion_id = fields.Int(allow_none=True)
    estado = fields.Str(validate=validate.OneOf([
        'PENDIENTE', 'APROBADA', 'RECHAZADA', 'EN_PROCESO',
        'PARCIAL', 'COMPLETADA', 'CANCELADA', 'VENCIDA'
    ]))
    fecha_emision = fields.Date(allow_none=True)
    fecha_estimada_entrega = fields.Date(allow_none=True)
    fecha_real_entrega = fields.Date(allow_none=True)
    prioridad = fields.Str(validate=validate.OneOf(['BAJA', 'NORMAL', 'ALTA', 'URGENTE']))
    subtotal = fields.Decimal(as_string=True, allow_none=True)
    iva = fields.Decimal(as_string=True, allow_none=True)
    total = fields.Decimal(as_string=True, allow_none=True)
    observaciones = fields.Str(allow_none=True)
    usuario_creador_id = fields.Int(required=True)
    usuario_aprobador_id = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    fecha_creacion = fields.DateTime(dump_only=True)