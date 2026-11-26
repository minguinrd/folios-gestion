"""Helpers de exportación Excel."""


def neutralizar_formulas(wb):
    """Fuerza a texto cualquier celda que openpyxl haya escrito como fórmula.

    openpyxl interpreta strings que empiezan con '=' como fórmula: un nombre de
    usuario/tipo con ``=HYPERLINK(...)`` se ejecutaría al abrir el .xlsx.
    Llamar justo antes de ``wb.save()``.
    """
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for celda in fila:
                if celda.data_type == 'f':
                    celda.data_type = 's'


def celda_segura(ws, valor, **estilo):
    """WriteOnlyCell que nunca queda como fórmula (para hojas write_only).

    En modo write_only no se puede recorrer la hoja después con
    neutralizar_formulas(): la neutralización va celda a celda al escribir.
    """
    from openpyxl.cell import WriteOnlyCell
    celda = WriteOnlyCell(ws, value=valor)
    if celda.data_type == 'f':
        celda.data_type = 's'
    for nombre, val in estilo.items():
        setattr(celda, nombre, val)
    return celda
