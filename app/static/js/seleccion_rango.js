// Selección de folios por rango para crear entrega/devolución.
//
// Marcar un rango de 200 folios con Ctrl+clic en una lista de miles es lento
// y propenso a errores: "Desde / Hasta" selecciona de una vez todos los folios
// cargados en #folio-select cuyo número cae en el rango. Las opciones tienen
// el texto "Folio <número> - <tipo>" (app/services/movimientos.py).
// Los inputs del rango no tienen name: no viajan en el POST.
(function () {
    'use strict';

    function numeroDe(opcion) {
        const m = opcion.text.match(/^Folio\s+(\d+)/);
        return m ? Number(m[1]) : null;
    }

    // Reemplaza la selección por las opciones que cumplen `predicado` y avisa
    // al formulario (contador/resumen escuchan 'change'). Devuelve cuántas.
    function seleccionar(select, predicado) {
        let n = 0;
        Array.from(select.options).forEach(function (o, i) {
            o.selected = !!predicado(o, i);
            if (o.selected) n++;
        });
        select.dispatchEvent(new Event('change', { bubbles: true }));
        return n;
    }

    function avisar(msg, texto, tipo) {
        if (!msg) return;
        msg.textContent = texto;
        msg.className = 'd-block small mb-2 ' + (tipo === 'error' ? 'text-danger' : 'text-success');
    }

    window.SeleccionFolios = { seleccionar: seleccionar, numeroDe: numeroDe, avisar: avisar };

    document.addEventListener('DOMContentLoaded', function () {
        const select = document.getElementById('folio-select');
        const desde = document.getElementById('rango-desde');
        const hasta = document.getElementById('rango-hasta');
        const boton = document.getElementById('rango-aplicar');
        const msg = document.getElementById('rango-msg');
        if (!select || !desde || !hasta || !boton) return;

        function aplicar() {
            const a = parseInt(desde.value, 10);
            const b = parseInt(hasta.value, 10) || a;  // solo "Desde" = un folio
            if (!a || a < 1 || b < a) {
                avisar(msg, 'Ingrese un rango válido: "Desde" debe ser menor o igual que "Hasta".', 'error');
                return;
            }
            if (!select.options.length) {
                avisar(msg, 'Primero elija el tipo de certificado para cargar los folios.', 'error');
                return;
            }
            const n = seleccionar(select, function (o) {
                const num = numeroDe(o);
                return num !== null && num >= a && num <= b;
            });
            const pedidos = b - a + 1;
            if (!n) {
                avisar(msg, 'Ningún folio de ese rango está en la lista.', 'error');
            } else if (n < pedidos) {
                avisar(msg, 'Se seleccionaron ' + n + ' de ' + pedidos +
                       ' números del rango: los demás no están en la lista.', 'error');
            } else {
                avisar(msg, 'Se seleccionaron los ' + n + ' folios del rango.', 'ok');
            }
        }

        boton.addEventListener('click', aplicar);
        // Enter en los campos aplica el rango en vez de enviar el formulario.
        [desde, hasta].forEach(function (campo) {
            campo.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); aplicar(); }
            });
        });
    });
})();
