from marshmallow import Schema, fields, validate
from decimal import Decimal

class BloqueoCapacidadSchema(Schema):
    """
    Schema para validar los datos de bloqueos de capacidad.
    """
    id = fields.Int(
        dump_only=True
    )
    centro_trabajo_id = fields.Int(
        required=True,
        error_messages={"required": "Debe seleccionar un centro de trabajo (línea)."}
    )
    fecha = fields.Date(
        required=True,
        error_messages={"required": "La fecha es obligatoria."}
    )
    minutos_bloqueados = fields.Decimal(
        required=True,
        as_string=True, # Usar string para mantener la precisión de Decimal
        validate=validate.Range(min=Decimal("0.01")),
        error_messages={
            "required": "Los minutos a bloquear son obligatorios.",
            "validator_failed": "Los minutos deben ser un número positivo."
        }
    )
    motivo = fields.Str(
        allow_none=True,
        validate=validate.Length(max=255)
    )
    created_at = fields.DateTime(
        dump_only=True
    )

    # Campo extra para el JOIN (leído desde el modelo get_all_with_details)
    nombre_centro = fields.Str(dump_only=True)