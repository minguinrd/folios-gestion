from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SelectField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.form_fields import FechaLatinaField, NoFutura
from app.utils import coerce_id_opcional


def _limpiar(valor):
    """Recorta y colapsa espacios; vacío → None (no se guarda '')."""
    if valor is None:
        return None
    valor = ' '.join(valor.split())
    return valor or None


class EntregaCreateForm(FlaskForm):
    folio_ids = SelectMultipleField('Folios', coerce=int, validators=[
        DataRequired(message='Seleccione al menos un folio.'),
    ])
    fechaEntrega = FechaLatinaField('Fecha de Entrega', validators=[
        DataRequired(message='Seleccione una fecha.'),
        NoFutura(),
    ])
    centroId = SelectField('Centro de Salud', coerce=coerce_id_opcional,
                           validators=[DataRequired(message='Seleccione el centro de salud.')])
    recibidoPor = StringField('Recibido por', filters=[_limpiar], validators=[
        DataRequired(message='Indique el nombre de quien recibe los folios.'),
        Length(max=120, message='Máximo 120 caracteres.'),
    ])
    submit = SubmitField('Registrar Entrega')


class EntregaEditForm(FlaskForm):
    folio_id = SelectField('Folio', coerce=int, validators=[
        DataRequired(message='Seleccione un folio.'),
    ])
    fechaEntrega = FechaLatinaField('Fecha de Entrega', validators=[
        DataRequired(message='Seleccione una fecha.'),
        NoFutura(),
    ])
    centroId = SelectField('Centro de Salud', coerce=int,
                           validators=[DataRequired(message='Seleccione el centro de salud.')])
    # Opcional al editar: las entregas previas a la columna no lo tienen.
    recibidoPor = StringField('Recibido por', filters=[_limpiar], validators=[
        Optional(), Length(max=120, message='Máximo 120 caracteres.'),
    ])
    submit = SubmitField('Guardar')


class ImportarEntregaForm(FlaskForm):
    archivo = FileField('Archivo Excel (.xlsx)', validators=[
        FileRequired(message='Seleccione un archivo.'),
        FileAllowed(['xlsx'], message='El archivo debe ser un Excel (.xlsx).'),
    ])
    submit = SubmitField('Validar archivo')
