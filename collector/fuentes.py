"""
fuentes.py — de dónde sale cada clasificadora.

Con Firecrawl cada fuente es: darle la URL de listado y el rango, y recibir las
acciones ya estructuradas. Sin regex, sin Anthropic.
"""
from ia import extraer_acciones

FUENTES_URLS = {
    'Feller Rate': {
        'urls': ['https://www.feller-rate.com/cl/'],
        'sigilo': False, 'js': False,
    },
    'Humphreys': {
        'urls': ['https://humphreys.cl/noticias/',
                 'https://humphreys.cl/noticias/page/2/'],
        'sigilo': False, 'js': False,
    },
    "Moody's Local Chile": {
        'urls': ['https://moodyslocal.cl/reportes/acciones-de-calificacion/'],
        'sigilo': True, 'js': False,     # Cloudflare -> modo sigilo
    },
    'Fitch Chile': {
        'urls': ['https://www.fitchratings.com/search?'
                 'filter.country=Chile&filter.reportType=Rating+Action+Commentary'],
        'sigilo': True, 'js': True,      # SPA React -> esperar JS
    },
}


def recolectar_fuente(nombre, desde, hasta, log=print):
    cfg = FUENTES_URLS.get(nombre)
    if not cfg:
        return []
    acciones = []
    for url in cfg['urls']:
        try:
            log(f'   scrape+extrae {url}')
            filas = extraer_acciones(url, nombre, desde, hasta,
                                     esperar_js=cfg['js'], sigilo=cfg['sigilo'])
            log(f'   {len(filas)} acciones')
            for f in filas:
                f['clasificadora'] = nombre
                f['fuente_url'] = url
                acciones.append(f)
        except Exception as e:
            log(f'   ERROR: {e}')
    return acciones


CMF_CONSULTA = ('https://www.cmfchile.cl/institucional/estadisticas/'
                'valores_clasificaciones_asignadas.php')
