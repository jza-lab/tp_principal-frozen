from marshmallow import Schema, fields, validate, post_load, ValidationError
from datetime import date

class InsumosInventarioSchema(Schema):
    """Esquema para validación de inventario"""

    id_lote = fields.Str(dump_only=True)
    id_insumo = fields.Str(required=True, error_messages={'required': 'El ID del insumo es obligatorio'})
    id_proveedor = fields.Str(allow_none=True, load_default=None)
    usuario_ingreso = fields.Str(allow_none=True, load_default=None)

    numero_lote_proveedor = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        load_default=None
    )
    cantidad_inicial = fields.Float(
        required=True,
        validate=validate.Range(min=0.001),
        error_messages={"required": "La cantidad inicial es obligatoria"}
    )
    cantidad_actual = fields.Float(
        validate=validate.Range(min=0),
        allow_none=True,
        load_default=0.0
    )
    precio_unitario = fields.Float(
        validate=validate.Range(min=0),
        allow_none=True,
        load_default=None
    )
    costo_total = fields.Float(dump_only=True)

    # ✅ Cambiar a fields.Str y manejar la conversión en post_load
    f_ingreso = fields.Str(allow_none=True)
    f_vencimiento = fields.Str(allow_none=True, load_default=None)

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

    estado = fields.Str(
        validate=validate.OneOf(['disponible', 'reservado', 'agotado', 'vencido']),
        dump_only=True
    )
    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)

    @post_load
    def validate_fechas(self, data, **kwargs):
        """Validar fechas lógicas"""
        f_ingreso = data.get('f_ingreso')
        f_vencimiento = data.get('f_vencimiento')

        # Convertir strings a date para validación si es necesario
        if f_vencimiento and f_ingreso:
            try:
                # Si son strings, convertirlos a date para comparar
                if isinstance(f_ingreso, str):
                    f_ingreso = date.fromisoformat(f_ingreso)
                if isinstance(f_vencimiento, str):
                    f_vencimiento = date.fromisoformat(f_vencimiento)

                if f_vencimiento < f_ingreso:
                    raise ValidationError('La fecha de vencimiento no puede ser anterior al ingreso')
            except (ValueError, TypeError):
                # Si hay error en la conversión, la validación fallará en otro lugar
                pass

        return data

    @post_load
    def set_defaults(self, data, **kwargs):
        """Establecer valores por defecto"""
        if not data.get('f_ingreso'):
            # ✅ Siempre devolver string ISO
            data['f_ingreso'] = date.today().isoformat()

        if not data.get('cantidad_actual'):
            data['cantidad_actual'] = data['cantidad_inicial']

        # ✅ Asegurar que las fechas sean strings
        if isinstance(data.get('f_ingreso'), date):
            data['f_ingreso'] = data['f_ingreso'].isoformat()
        if isinstance(data.get('f_vencimiento'), date):
            data['f_vencimiento'] = data['f_vencimiento'].isoformat()

        return data