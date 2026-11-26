# Librerías de terceros servidas localmente

Antes se cargaban desde CDN (jsDelivr, cdnjs, code.jquery.com, datatables.net,
Google Fonts): en una red con internet lenta o filtrada la app perdía estilos,
íconos, calendarios y diálogos. Cada archivo es **idéntico byte a byte** al del
CDN (verificado contra el hash SRI que ya usaban las plantillas, que se conserva
en el atributo `integrity`). La versión va en la ruta: para actualizar, agregue
la carpeta de la versión nueva, cambie la ruta y el `integrity` en la plantilla
y borre la vieja.

| Librería | Versión | Origen | Licencia |
|----------|---------|--------|----------|
| Bootstrap (CSS + bundle JS) | 5.3.3 | cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist | MIT |
| Font Awesome Free (CSS + webfonts) | 6.5.1 | cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1 | CSS: MIT · fuentes: SIL OFL 1.1 · íconos: CC BY 4.0 |
| jQuery | 3.7.1 | code.jquery.com/jquery-3.7.1.min.js | MIT |
| SweetAlert2 | 11.26.25 | cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.all.min.js | MIT |
| flatpickr (+ l10n es) | 4.6.13 | cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist | MIT |
| DataTables (+ integración Bootstrap 5) | 1.13.7 | cdn.datatables.net/1.13.7 | MIT |
| Chart.js | 4.4.1 | cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js | MIT |
| Fira Sans / Fira Code (latin, latin-ext) | Google Fonts | fonts.googleapis.com | SIL OFL 1.1 |

**SweetAlert2 se fija en 11.26.25.** La plantilla pedía `sweetalert2@11`
(versión flotante) con un hash de integridad fijo: cuando el CDN pasó a servir
11.26.26 el hash dejó de coincidir y los navegadores bloqueaban el script (sin
diálogos de confirmación). Nunca usar versiones flotantes con `integrity`.
