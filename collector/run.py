#!/usr/bin/env python3
"""
run.py — recolector con IA.

  python run.py                     ultima semana (lunes a hoy, o 7 dias)
  python run.py --dias 14
  python run.py --desde 2026-07-13 --hasta 2026-07-24
  python run.py --solo "Feller Rate,Humphreys"
  python run.py --con-resumen       ademas genera el resumen de 4 puntos con IA

Requiere las variables de entorno FIRECRAWL_API_KEY y ANTHROPIC_API_KEY.
Ver LEEME para configurarlas en tu Mac.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuentes import FUENTES_URLS, recolectar_fuente          # noqa: E402
from ia import scrape                                          # noqa: E402
from ia import extraer_acciones  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, 'data')
SALIDA = os.path.join(DATA, 'clasificaciones.json')
ALIAS = os.path.join(DATA, 'alias_emisores.json')




# Esquema de resumen de 4 puntos, extraido del PDF por Firecrawl.
_ESQUEMA_RESUMEN = {
    "type": "object",
    "properties": {
        "accion": {"type": "string", "description": "Qué hizo la clasificadora con la nota (1-2 frases)"},
        "fundamentos": {"type": "string", "description": "Por qué; factores de la clasificación"},
        "desempeno": {"type": "string", "description": "Desempeño financiero con cifras concretas del texto"},
        "riesgos": {"type": "string", "description": "Qué podría gatillar un cambio de nota"},
    },
    "required": ["accion", "fundamentos", "desempeno", "riesgos"],
}


def _resumir_pdf(url, emisor):
    """Resumen de 4 puntos usando la extraccion con esquema de Firecrawl."""
    from ia import _post
    prompt = (f"Este es un comunicado de clasificación de riesgo de {emisor}. "
              "Resume en cuatro bloques breves y factuales, en español, citando "
              "las cifras concretas que aparezcan (ingresos, EBITDA, deuda/EBITDA, "
              "cobertura, márgenes). No inventes datos que no estén.")
    data = _post({'url': url, 'formats': ['json'], 'timeout': 60000,
                  'jsonOptions': {'schema': _ESQUEMA_RESUMEN, 'prompt': prompt}})
    obj = (data.get('data', {}) or {}).get('json', {}) or {}
    if isinstance(obj, dict) and obj.get('accion'):
        return {k: obj.get(k, '') for k in ('accion', 'fundamentos', 'desempeno', 'riesgos')}
    return None


def clave_emisor(nombre: str) -> str:
    if not nombre:
        return ''
    n = ''.join(c for c in unicodedata.normalize('NFD', nombre)
                if unicodedata.category(c) != 'Mn').lower()
    n = re.sub(r'\b(s\.?a\.?|spa|ltda\.?|limitada|compania|cia)\b', ' ', n)
    return re.sub(r'[^a-z0-9]+', ' ', n).strip()


def id_registro(r: dict) -> str:
    semilla = f"{r.get('clasificadora')}|{r.get('fecha')}|{r.get('emisor')}|{r.get('actual')}"
    return hashlib.sha1(semilla.encode()).hexdigest()[:14]


def cargar(ruta, defecto):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return defecto


def semana_actual():
    """Lunes de esta semana hasta hoy. Hoy viernes 24 -> 20 al 24; pero el
    usuario pidio 'la ultima semana y esta', asi que tomamos 11 dias atras
    para cubrir la semana pasada + la actual."""
    hoy = dt.date.today()
    desde = hoy - dt.timedelta(days=11)
    return desde.isoformat(), hoy.isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dias', type=int)
    ap.add_argument('--desde')
    ap.add_argument('--hasta')
    ap.add_argument('--solo', default='')
    ap.add_argument('--con-resumen', action='store_true')
    a = ap.parse_args()

    if a.desde or a.hasta:
        hasta = a.hasta or dt.date.today().isoformat()
        desde = a.desde or (dt.date.fromisoformat(hasta) - dt.timedelta(days=7)).isoformat()
    elif a.dias:
        hasta = dt.date.today().isoformat()
        desde = (dt.date.today() - dt.timedelta(days=a.dias)).isoformat()
    else:
        desde, hasta = semana_actual()

    pedidas = [s.strip() for s in a.solo.split(',') if s.strip()] or list(FUENTES_URLS)
    os.makedirs(DATA, exist_ok=True)
    alias = cargar(ALIAS, {})
    previos = {r['id']: r for r in cargar(SALIDA, {}).get('acciones', [])}

    print(f'Rango: {desde} a {hasta}\n')
    crudas = []
    for nombre in pedidas:
        print(f'-> {nombre}')
        crudas += recolectar_fuente(nombre, desde, hasta)

    salida = []
    for c in crudas:
        emisor = alias.get(clave_emisor(c.get('emisor', '')), c.get('emisor'))
        reg = {
            'id': id_registro(c),
            'fecha': c.get('fecha'),
            'emisor': emisor,
            'emisor_dudoso': not bool(emisor),
            'instrumento': c.get('instrumento', ''),
            'clasificadora': c.get('clasificadora'),
            'escala': c.get('escala', 'largo'),
            'anterior': c.get('anterior'),
            'actual': c.get('actual'),
            'perspectiva': c.get('perspectiva'),
            'accion': c.get('accion', 'mantiene'),
            'titular': c.get('titular', ''),
            'documento_url': c.get('documento_url'),
            'fuente_url': c.get('fuente_url'),
            'indicadores': [],
            'resumen': None,
        }
        # Reusar resumen ya generado en corridas anteriores.
        viejo = previos.get(reg['id'])
        if viejo and viejo.get('resumen'):
            reg['resumen'] = viejo['resumen']
        elif a.con_resumen and reg['documento_url']:
            try:
                print(f"   resumen: {emisor}")
                reg['resumen'] = _resumir_pdf(reg['documento_url'], emisor or '')
            except Exception as e:
                print(f'   resumen falló: {e}')
        if reg['fecha'] and reg['actual']:
            salida.append(reg)

    # Fusionar con lo previo, dedup por id
    fusion = {r['id']: r for r in cargar(SALIDA, {}).get('acciones', [])}
    fusion.update({r['id']: r for r in salida})
    acciones = sorted(fusion.values(),
                      key=lambda r: (r['fecha'], r['clasificadora']), reverse=True)

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump({'generado': dt.datetime.now().astimezone().isoformat(),
                   'rango': {'desde': desde, 'hasta': hasta},
                   'acciones': acciones}, f, ensure_ascii=False, indent=1)

    print(f'\n{len(salida)} nuevas en el rango, {len(acciones)} en total -> {SALIDA}')
    if not salida:
        print('Ninguna acción nueva. Revisa que las API keys estén configuradas '
              '(FIRECRAWL_API_KEY, ANTHROPIC_API_KEY) y que el rango tenga datos.')


if __name__ == '__main__':
    main()
