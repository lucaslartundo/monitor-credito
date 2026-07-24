#!/usr/bin/env python3
"""
Recolector de acciones de clasificacion de riesgo (Chile).

  python run.py                      ultimos 30 dias
  python run.py --dias 120
  python run.py --desde 2026-01-01 --hasta 2026-07-24
  python run.py --solo humphreys,feller
  python run.py --con-resumen        ademas baja el PDF y extrae cifras + 4 puntos

Por defecto NO se descarga ningun PDF: el JSON queda con el link al informe en
el sitio de la clasificadora y nada mas. Es lo apropiado para un repositorio
publico, porque no se republica contenido ajeno.

Con --con-resumen se baja el PDF en memoria, se extraen las cifras y los cuatro
bloques, y ese texto queda guardado en el JSON. Usalo solo si el repositorio es
privado o interno.

Escribe data/clasificaciones.json y mantiene data/historial.json, que es lo
que permite saber la nota ANTERIOR cuando el titular no la menciona.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import unicodedata

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agencies import FUENTES, UA           # noqa: E402
from parse import analizar, normalizar     # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, 'data')
SALIDA = os.path.join(DATA, 'clasificaciones.json')
HISTORIAL = os.path.join(DATA, 'historial.json')
ALIAS = os.path.join(DATA, 'alias_emisores.json')


# --------------------------------------------------------------------------
# Identidad estable de cada registro
# --------------------------------------------------------------------------
def clave_emisor(nombre: str) -> str:
    """Normaliza el nombre para poder cruzar el mismo emisor entre agencias."""
    if not nombre:
        return ''
    n = ''.join(c for c in unicodedata.normalize('NFD', nombre)
                if unicodedata.category(c) != 'Mn').lower()
    n = re.sub(r'\b(s\.?a\.?|spa|ltda\.?|limitada|s\.?a\.?g\.?r\.?|'
               r'compania|cia|sociedad anonima|s\.?a\.?c\.?i\.?)\b', ' ', n)
    return re.sub(r'[^a-z0-9]+', ' ', n).strip()


def id_registro(r: dict) -> str:
    if r.get('id'):
        return r['id']
    semilla = f"{r['clasificadora']}|{r['fecha']}|{r.get('titular', '')[:120]}"
    return hashlib.sha1(semilla.encode()).hexdigest()[:14]


# --------------------------------------------------------------------------
# PDF -> cifras y resumen de 4 puntos
# --------------------------------------------------------------------------
# Numeros chilenos: 385.374 / 8,8% / 1,66 veces / $ 2,33 billones
NUM = r'\$?\s?\d{1,3}(?:\.\d{3})*(?:,\d+)?'

PATRONES_CIFRA = [
    ('Ingresos',              rf'ingresos[^.]{{0,60}}?({NUM})\s*(millones|mil millones|billones|MM\$?)?'),
    ('EBITDA',                rf'\bEBITDA[^.]{{0,60}}?({NUM})\s*(millones|billones|MM\$?)?'),
    ('Deuda financiera',      rf'deuda financiera[^.]{{0,60}}?({NUM})\s*(millones|billones|MM\$?)?'),
    ('Patrimonio',            rf'patrimonio[^.]{{0,60}}?({NUM})\s*(millones|billones|MM\$?)?'),
    ('Utilidad',              rf'utilidad[^.]{{0,60}}?({NUM})\s*(millones|billones|MM\$?)?'),
    ('Margen EBITDA',         rf'margen EBITDA[^.]{{0,40}}?({NUM})\s*%'),
    ('Margen NOI',            rf'margen NOI[^.]{{0,40}}?({NUM})\s*%'),
    ('Cobertura',             rf'cobertura[^.]{{0,60}}?({NUM})\s*(veces|x)'),
    ('Deuda / EBITDA',        rf'(?:deuda[^.]{{0,20}}(?:sobre|/)\s*EBITDA)[^.]{{0,40}}?({NUM})\s*(veces|x)?'),
    ('Presencia bursátil',    rf'presencia[^.]{{0,40}}?({NUM})\s*%'),
]

# Encabezados tipicos donde arranca cada uno de los 4 bloques.
SECCIONES = [
    ('accion',      r'(?:se\s+)?(?:asigna|ratifica|mantiene|confirma|sube|baja|aumenta|'
                    r'disminuye|modifica|retira|clasifica)\b'),
    ('fundamentos', r'(?:fundament|sustent|principales fortalezas|argumentos que sustentan|'
                    r'la clasificaci[oó]n se (?:apoya|sustenta|explica))'),
    ('desempeno',   r'(?:desempe[nñ]o|durante \d{4}|a (?:marzo|junio|septiembre|diciembre)|'
                    r'los ingresos alcanzaron|resultados)'),
    ('riesgos',     r'(?:riesgos?|se ve limitada|limitan la clasificaci|'
                    r'factores? que podr[ií]an|podr[ií]a ser revisada)'),
]


def texto_pdf(url: str) -> str:
    from pdfminer.high_level import extract_text
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    txt = extract_text(io.BytesIO(r.content)) or ''
    return re.sub(r'[ \t]*\n[ \t]*', '\n', txt)


def cifras_de(texto: str):
    """Saca cifras del comunicado. Solo lo que aparece explicito."""
    plano = re.sub(r'\s+', ' ', texto)
    vistas, out = set(), []
    for etiqueta, patron in PATRONES_CIFRA:
        for m in re.finditer(patron, plano, re.I):
            valor = m.group(1).strip()
            unidad = (m.lastindex and m.lastindex >= 2 and m.group(2)) or ''
            if etiqueta.startswith('Margen') or 'Presencia' in etiqueta:
                v = f'{valor}%'
            elif 'veces' in patron or 'EBITDA' in etiqueta and 'x' in (unidad or ''):
                v = f'{valor}x'
            else:
                v = f'{valor} {unidad}'.strip()
            # periodo, si esta cerca
            ctx = plano[max(0, m.start() - 120): m.end() + 60]
            pm = re.search(r'\b(?:a\s+)?(?:(marzo|junio|septiembre|diciembre)\s+de\s+)?(20\d{2})\b', ctx, re.I)
            periodo = ((pm.group(1) + ' ' if pm.group(1) else '') + pm.group(2)) if pm else ''
            k = (etiqueta, v, periodo)
            if k in vistas:
                continue
            vistas.add(k)
            out.append({'l': etiqueta, 'v': v, 'p': periodo})
            if len(out) >= 14:
                return out
    return out


def resumen_de(texto: str):
    """
    Parte el comunicado en los 4 bloques. Es extraccion, no redaccion: toma
    las frases del propio informe. Si un bloque no aparece, queda vacio y el
    front lo muestra como pendiente en vez de rellenar con humo.
    """
    parrafos = [normalizar(p) for p in re.split(r'\n\s*\n', texto) if len(p.strip()) > 90]
    if not parrafos:
        return None
    res = {k: [] for k, _ in SECCIONES}
    for p in parrafos:
        for clave, patron in SECCIONES:
            if re.search(patron, p, re.I):
                res[clave].append(p)
                break
    salida = {}
    for clave, _ in SECCIONES:
        trozos = res[clave][:3]
        salida[clave] = ' '.join(trozos)[:1400] if trozos else ''
    return salida if any(salida.values()) else None


# --------------------------------------------------------------------------
def cargar(ruta, defecto):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return defecto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dias', type=int, default=30)
    ap.add_argument('--desde')
    ap.add_argument('--hasta')
    ap.add_argument('--solo', default='')
    ap.add_argument('--con-resumen', action='store_true',
                    help='baja el PDF y guarda cifras y resumen (solo repos privados)')
    a = ap.parse_args()

    hasta = a.hasta or dt.date.today().isoformat()
    desde = a.desde or (dt.date.fromisoformat(hasta) - dt.timedelta(days=a.dias)).isoformat()
    pedidas = [s.strip() for s in a.solo.split(',') if s.strip()] or list(FUENTES)

    os.makedirs(DATA, exist_ok=True)
    historial = cargar(HISTORIAL, {})          # clave_emisor+instrumento -> [{fecha, nota}]
    alias = cargar(ALIAS, {})                  # correcciones manuales de nombre
    previos = {r['id']: r for r in cargar(SALIDA, {}).get('acciones', [])}

    crudos = []
    for nombre in pedidas:
        fn = FUENTES.get(nombre)
        if not fn:
            print(f'  fuente desconocida: {nombre}')
            continue
        print(f'-> {nombre} ({desde} a {hasta})')
        try:
            filas = fn(desde, hasta)
            print(f'   {len(filas)} registros')
            crudos += filas
        except Exception as e:
            print(f'   ERROR en {nombre}: {e}')

    salida, sin_emisor = [], 0
    for c in crudos:
        an = analizar(c.get('titular', ''), c.get('emisor'))
        emisor = alias.get(clave_emisor(an['emisor'] or ''), an['emisor'])
        if not emisor:
            sin_emisor += 1
        rid = id_registro(c)

        # Nota anterior: primero la del titular; si no, la ultima del historial.
        hkey = f"{clave_emisor(emisor)}|{an['escala']}"
        anterior = an['anterior']
        if not anterior:
            pasadas = [h for h in historial.get(hkey, []) if h['fecha'] < c['fecha']]
            if pasadas:
                anterior = sorted(pasadas, key=lambda h: h['fecha'])[-1]['nota']

        reg = {
            'id': rid,
            'fecha': c['fecha'],
            'emisor': emisor,
            'emisor_dudoso': emisor is None,
            'instrumento': c.get('instrumento') or '',
            'clasificadora': c['clasificadora'],
            'escala': an['escala'],
            'anterior': anterior,
            'actual': an['actual'],
            'perspectiva': an['perspectiva'],
            'accion': an['accion'],
            'titular': an['titular'],
            'documento_url': c.get('documento_url'),
            'fuente_url': c.get('fuente_url'),
            'indicadores': [],
            'resumen': None,
        }

        # Solo se toca el PDF si el usuario lo pide explicitamente.
        if a.con_resumen:
            viejo = previos.get(rid)
            if viejo and viejo.get('resumen'):
                reg['resumen'] = viejo['resumen']
                reg['indicadores'] = viejo.get('indicadores', [])
            elif reg['documento_url']:
                try:
                    t = texto_pdf(reg['documento_url'])
                    reg['resumen'] = resumen_de(t)
                    reg['indicadores'] = cifras_de(t)
                    print(f"   PDF ok: {emisor} ({len(reg['indicadores'])} cifras)")
                except Exception as e:
                    print(f'   PDF falló ({emisor}): {e}')

        if an['actual']:
            historial.setdefault(hkey, [])
            if not any(h['fecha'] == c['fecha'] and h['nota'] == an['actual']
                       for h in historial[hkey]):
                historial[hkey].append({'fecha': c['fecha'], 'nota': an['actual']})
        salida.append(reg)

    # Fusionar con lo que ya existia y deduplicar por id.
    fusion = {r['id']: r for r in cargar(SALIDA, {}).get('acciones', [])}
    fusion.update({r['id']: r for r in salida})
    acciones = sorted(fusion.values(), key=lambda r: (r['fecha'], r['clasificadora']), reverse=True)

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump({'generado': dt.datetime.now().astimezone().isoformat(),
                   'rango': {'desde': desde, 'hasta': hasta},
                   'acciones': acciones}, f, ensure_ascii=False, indent=1)
    with open(HISTORIAL, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=1)

    modo = 'link + resumen extraido del PDF' if a.con_resumen else 'solo link al informe'
    print(f'\n{len(salida)} nuevos, {len(acciones)} en total -> {SALIDA}')
    print(f'modo: {modo}')
    if sin_emisor:
        print(f'{sin_emisor} sin emisor identificado. Agrégalos a data/alias_emisores.json')


if __name__ == '__main__':
    main()
