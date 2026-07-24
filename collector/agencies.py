"""
Un extractor por clasificadora.

Cada uno devuelve una lista de dicts crudos con al menos:
  fecha (YYYY-MM-DD), emisor, titular, documento_url, fuente_url, clasificadora

El parseo de la nota lo hace parse.analizar() despues, en run.py.
"""
import datetime as dt
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from parse import normalizar

UA = {'User-Agent': 'monitor-clasificaciones/1.0 (uso interno; contacto: tu-email)'}
TIMEOUT = 30


def _get(url, **kw):
    """GET con reintento y pausa. Los sitios chicos se caen si los apuras."""
    for intento in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, **kw)
            r.raise_for_status()
            time.sleep(0.7)
            return r
        except Exception:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))


def _iso(d, m, y):
    return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'


# ==========================================================================
# HUMPHREYS  —  humphreys.cl
# WordPress. Los comunicados son posts de la categoria "comunicados" y el PDF
# va enlazado dentro del contenido. Es la fuente mas limpia de las cuatro:
# el titulo del post es el emisor y el excerpt es el titular de la accion.
# ==========================================================================
def humphreys(desde: str, hasta: str):
    base = 'https://humphreys.cl'
    out = []

    # Camino 1: API REST de WordPress.
    try:
        cats = _get(f'{base}/wp-json/wp/v2/categories', params={'slug': 'comunicados'}).json()
        cat_id = cats[0]['id'] if cats else None
        pagina, seguir = 1, True
        while seguir and pagina <= 20:
            r = _get(f'{base}/wp-json/wp/v2/posts', params={
                'categories': cat_id, 'per_page': 100, 'page': pagina,
                'after': f'{desde}T00:00:00', 'before': f'{hasta}T23:59:59',
                'orderby': 'date', 'order': 'desc'})
            posts = r.json()
            if not posts:
                break
            for p in posts:
                html = p.get('content', {}).get('rendered', '')
                pdf = None
                m = re.search(r'href="([^"]+\.pdf)"', html, re.I)
                if m:
                    pdf = urljoin(base, m.group(1))
                excerpt = BeautifulSoup(p.get('excerpt', {}).get('rendered', ''),
                                        'html.parser').get_text(' ')
                titulo = BeautifulSoup(p.get('title', {}).get('rendered', ''),
                                       'html.parser').get_text(' ')
                out.append({
                    'clasificadora': 'Humphreys',
                    'fecha': p['date'][:10],
                    'emisor': normalizar(titulo),
                    'titular': normalizar(excerpt) or normalizar(titulo),
                    'documento_url': pdf,
                    'fuente_url': p.get('link'),
                    'id': f"hum-{p['id']}",
                })
            pagina += 1
            seguir = len(posts) == 100
        if out:
            return out
    except Exception as e:
        print(f'  [Humphreys] REST no disponible ({e}); paso a HTML')

    # Camino 2: HTML paginado de /noticias/.
    pagina = 1
    while pagina <= 30:
        url = f'{base}/noticias/' if pagina == 1 else f'{base}/noticias/page/{pagina}/'
        try:
            soup = BeautifulSoup(_get(url).text, 'html.parser')
        except Exception:
            break
        items = soup.select('article, .noticia, .post')
        if not items:
            break
        antes_del_rango = 0
        for it in items:
            txt = it.get_text(' ', strip=True)
            fm = re.search(r'(\d{2})/(\d{2})/(\d{4})', txt)
            if not fm:
                continue
            fecha = _iso(fm.group(1), fm.group(2), fm.group(3))
            if fecha > hasta:
                continue
            if fecha < desde:
                antes_del_rango += 1
                continue
            h = it.find(['h2', 'h3', 'h4'])
            a_pdf = it.find('a', href=re.compile(r'\.pdf$', re.I))
            out.append({
                'clasificadora': 'Humphreys',
                'fecha': fecha,
                'emisor': normalizar(h.get_text(' ', strip=True)) if h else None,
                'titular': normalizar(txt),
                'documento_url': urljoin(base, a_pdf['href']) if a_pdf else None,
                'fuente_url': url,
                'id': None,
            })
        if antes_del_rango >= len(items):
            break
        pagina += 1
    return out


# ==========================================================================
# MOODY'S LOCAL CHILE  —  moodyslocal.cl   (ex ICR)
# WordPress con custom post type "rating-action". La tabla de
# /reportes/acciones-de-calificacion/ los lista todos; la REST es mas rapida.
# El titular trae con frecuencia la nota anterior Y la nueva.
# ==========================================================================
def moodys(desde: str, hasta: str):
    base = 'https://moodyslocal.cl'
    out = []

    for endpoint in ('rating-action', 'rating_action'):
        try:
            pagina, seguir = 1, True
            while seguir and pagina <= 20:
                r = _get(f'{base}/wp-json/wp/v2/{endpoint}', params={
                    'per_page': 100, 'page': pagina,
                    'after': f'{desde}T00:00:00', 'before': f'{hasta}T23:59:59',
                    'orderby': 'date', 'order': 'desc'})
                posts = r.json()
                if not isinstance(posts, list) or not posts:
                    break
                for p in posts:
                    titulo = BeautifulSoup(p.get('title', {}).get('rendered', ''),
                                           'html.parser').get_text(' ')
                    html = p.get('content', {}).get('rendered', '')
                    m = re.search(r'href="([^"]+\.pdf)"', html, re.I)
                    out.append({
                        'clasificadora': "Moody's Local Chile",
                        'fecha': p['date'][:10],
                        'emisor': None,               # se infiere del titular
                        'titular': normalizar(titulo),
                        'documento_url': urljoin(base, m.group(1)) if m else None,
                        'fuente_url': p.get('link'),
                        'id': f"mdy-{p['id']}",
                    })
                pagina += 1
                seguir = len(posts) == 100
            if out:
                return out
        except Exception:
            continue

    print("  [Moody's] REST no disponible; leo la tabla HTML")
    url = f'{base}/reportes/acciones-de-calificacion/'
    soup = BeautifulSoup(_get(url).text, 'html.parser')
    for tr in soup.select('table tr'):
        celdas = tr.find_all('td')
        if len(celdas) < 2:
            continue
        fm = re.search(r'(\d{2})/(\d{2})/(\d{4})', celdas[0].get_text())
        if not fm:
            continue
        fecha = _iso(fm.group(1), fm.group(2), fm.group(3))
        if not (desde <= fecha <= hasta):
            continue
        a = celdas[1].find('a')
        out.append({
            'clasificadora': "Moody's Local Chile",
            'fecha': fecha,
            'emisor': None,
            'titular': normalizar(celdas[1].get_text(' ', strip=True)),
            'documento_url': None,
            'fuente_url': a['href'] if a and a.get('href') else url,
            'id': None,
        })
    return out


# ==========================================================================
# FELLER RATE  —  feller-rate.com/cl
# El listado "Noticias" del home trae emisor, titular y fecha en un mismo
# bloque, con el formato:  "Emisor (CL) Feller Rate <accion>. dd-mm-aaaa"
# El PDF exige registro gratuito, asi que guardamos el link al comunicado.
# ==========================================================================
_FELLER = re.compile(
    r'^(?P<emisor>.+?)\s*\((?:CL|PY|DO|SV|CR|PA)\)\s*'
    r'(?P<titular>.+?)\s*(?P<f>\d{2}-\d{2}-\d{4})\s*$', re.S)


def feller(desde: str, hasta: str, max_paginas: int = 15):
    base = 'https://www.feller-rate.com'
    out, vistos = [], set()

    for pagina in range(1, max_paginas + 1):
        url = f'{base}/cl/' if pagina == 1 else f'{base}/cl/?pag={pagina}'
        try:
            soup = BeautifulSoup(_get(url).text, 'html.parser')
        except Exception:
            break

        enlaces = soup.select('a[href*="/clasificacion-cp/"]')
        if not enlaces:
            break

        nuevos = 0
        fuera_por_antiguedad = 0
        for a in enlaces:
            href = urljoin(base, a['href'])
            if href in vistos:
                continue
            m = _FELLER.match(normalizar(a.get_text(' ', strip=True)))
            if not m:
                continue
            vistos.add(href)
            nuevos += 1
            d, mo, y = m.group('f').split('-')
            fecha = _iso(d, mo, y)
            if fecha > hasta:
                continue
            if fecha < desde:
                fuera_por_antiguedad += 1
                continue
            out.append({
                'clasificadora': 'Feller Rate',
                'fecha': fecha,
                'emisor': m.group('emisor').strip(),
                'titular': m.group('titular').strip(),
                'documento_url': None,      # tras registro gratuito
                'fuente_url': href,
                'id': 'fel-' + re.sub(r'\D', '-', a['href']).strip('-'),
            })
        # Si toda la pagina ya quedo antes del rango, no sigo retrocediendo.
        if nuevos and fuera_por_antiguedad == nuevos:
            break
    return out


# ==========================================================================
# FITCH CHILE  —  fitchratings.com
# La busqueda es una SPA en React: el HTML que llega no trae los resultados,
# se cargan por XHR despues. Sin navegador headless ni credenciales de su API
# no hay extraccion confiable, y prefiero devolver vacio antes que inventar.
#
# Dos caminos, ninguno gratis:
#   a) Playwright en el runner de GitHub Actions (agrega ~40 s por corrida)
#   b) Suscribirse al RSS/feed comercial de Fitch
#
# Mientras tanto, las acciones de Fitch se rescatan por el repositorio de
# la CMF, donde los comunicados quedan depositados con algunos dias de rezago.
# ==========================================================================
def fitch(desde: str, hasta: str):
    print('  [Fitch] omitido: la busqueda es SPA. Ver nota en agencies.py')
    return []


FUENTES = {
    'humphreys': humphreys,
    'moodys': moodys,
    'feller': feller,
    'fitch': fitch,
}
