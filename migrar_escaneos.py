"""Mueve escaneos del layout anterior al actual.

Antes:  <SCANS_FOLDER>/<anio>/<numero>.jpg
Ahora:  <SCANS_FOLDER>/<anio>/<tipo_id>/<numero>.jpg

Solo se mueven los archivos cuyo (año, número) corresponde a UN único folio.
Los ambiguos (mismo número y año en varios tipos), los que no tienen folio y
los que chocan con un archivo ya existente se dejan en su lugar y se listan.

Uso:
    python3 migrar_escaneos.py            # simulación: solo informa
    python3 migrar_escaneos.py --aplicar  # mueve los archivos
En Docker:  docker compose exec app python migrar_escaneos.py [--aplicar]

Después de aplicar, ejecute "Validar Escaneados" en Folios.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.escaneos import migrar_legados


def build_parser():
    parser = argparse.ArgumentParser(
        description='Mueve escaneos <anio>/<n>.jpg a <anio>/<tipo_id>/<n>.jpg.')
    parser.add_argument('--aplicar', action='store_true',
                        help='mover de verdad (sin esto solo simula)')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    app = create_app()
    with app.app_context():
        reporte = migrar_legados(aplicar=args.aplicar)
    verbo = 'Movidos' if args.aplicar else 'Se moverían'
    print(f'{verbo}: {len(reporte["movidos"])}')
    for origen, destino in reporte['movidos']:
        print(f'  {origen} -> {destino}')
    for clave, titulo in (
            ('ambiguos', 'Ambiguos (varios tipos con ese año y número; mover a mano)'),
            ('sin_folio', 'Sin folio con ese año y número (se dejan)'),
            ('conflictos', 'Destino ya existe (no se sobrescribe)')):
        if reporte[clave]:
            print(f'{titulo}: {len(reporte[clave])}')
            for ruta in reporte[clave]:
                print(f'  {ruta}')
    if not args.aplicar and reporte['movidos']:
        print('Simulación: repita con --aplicar para mover los archivos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
