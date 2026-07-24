# Monitor de clasificaciones de riesgo · Chile

    index.html                  el front (GitHub Pages)
    collector/parse.py          titular -> accion, nota anterior, nota nueva, perspectiva
    collector/agencies.py       un extractor por clasificadora
    collector/run.py            orquestador: junta, resuelve historial, lee PDF, escribe JSON
    data/clasificaciones.json   lo genera el recolector
    data/historial.json         memoria de notas, permite calcular los notches
    data/alias_emisores.json    correcciones manuales de nombre

## Partir

    pip install -r collector/requirements.txt
    python collector/run.py --dias 180
    python -m http.server 8000       # abrir http://localhost:8000

## Que guarda el JSON

Por defecto: fecha, emisor, instrumento, clasificadora, nota anterior, nota
nueva, perspectiva, tipo de accion, el titular publicado y el LINK al informe.
Ningun PDF se descarga ni se copia al repositorio.

Con --con-resumen ademas se baja el PDF en memoria y se guardan las cifras y
los cuatro bloques de resumen. Ese texto sale del comunicado de la
clasificadora, asi que esa opcion es para repositorios privados o internos,
no para uno publico.

En GitHub: Settings -> Pages -> deploy desde la rama. El workflow corre de
lunes a viernes a las 08:00 de Chile y commitea data/.

## Estado por fuente

| Fuente              | Listado | PDF publico | Nota anterior en el titular |
|---------------------|---------|-------------|------------------------------|
| Humphreys           | si      | si          | no                           |
| Moody's Local Chile | si      | parcial     | frecuente                    |
| Feller Rate         | si      | no, registro| no                           |
| Fitch Chile         | no      | no          | -                            |

Fitch: la busqueda es una SPA en React, el HTML no trae resultados. Requiere
Playwright en el runner o acceso a su feed. Ver la nota en agencies.py.
