# Monitor de clasificaciones de riesgo · Chile (con IA)

Scrapea las cuatro clasificadoras (Feller Rate, Humphreys, Moody's Local,
Fitch Chile) usando IA: **Firecrawl** entra a cada sitio y **Anthropic** lee el
texto y arma los datos estructurados y el resumen de 4 puntos.

## Cómo se actualiza

**Doble clic en `actualizar.command`.** Recolecta la última semana y media,
genera los resúmenes y sube los datos a GitHub. La página se refresca sola.

Para otro rango:

    ./actualizar.command "--dias 30"
    ./actualizar.command "--desde 2026-07-13 --hasta 2026-07-24"

Sin argumentos toma por defecto los últimos 11 días (semana pasada + actual).

---

## Claves de API (se configuran una sola vez)

Crea un archivo llamado **`claves.env`** en esta carpeta, con tu clave real:

    FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxxxxx

Ese archivo **no se sube a GitHub** (está en `.gitignore`). Vive solo en tu Mac.

### Obtener la clave de Firecrawl (gratis)
1. Entra a https://firecrawl.dev y crea una cuenta (sin tarjeta).
2. En el dashboard, sección **API Keys**, copia tu clave (empieza con `fc-`).
3. El plan gratis da ~1.000 créditos al mes; una corrida usa 15-30. Te sobra.

Todo — scraping, extracción y resumen — lo hace Firecrawl. No se necesita
cuenta de Anthropic ni ninguna otra.

---

## Qué hace cada archivo

    index.html            la página (diseño BTG)
    collector/ia.py       Firecrawl + Anthropic
    collector/fuentes.py  URLs y extracción por clasificadora
    collector/run.py      orquesta, arma el JSON, sube
    data/clasificaciones.json   lo genera el recolector
    claves.env            tus API keys (NO se sube)

## El buscador y la CMF

Al escribir un emisor en el buscador de la página, aparece un enlace directo al
registro oficial de la CMF para ese emisor, donde está el documento más reciente.

## La fuente BTG Pactual Sans

La página pide "BTG Pactual Sans". Si tienes los archivos de la fuente del brand
center, ponlos en `assets/` como `BTGPactualSans.woff2`. Si no, cae a Inter.
