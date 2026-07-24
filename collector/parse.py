"""
Convierte el titular de una clasificadora en datos estructurados.

Este es el corazon del recolector. Los cuatro sitios publican el titular con
la misma gramatica: un verbo que indica la accion, una o dos notas, y la
tendencia. De ahi sale todo salvo las cifras, que vienen del PDF.
"""
import re
import unicodedata

# --------------------------------------------------------------------------
# Normalizacion
# --------------------------------------------------------------------------
COMILLAS = dict.fromkeys(map(ord, '\u201c\u201d\u2018\u2019\u00ab\u00bb\u201e\u201f'), '"')


def normalizar(t: str) -> str:
    """Comillas curvas a rectas, espacios raros a espacio simple."""
    t = unicodedata.normalize('NFC', t or '')
    t = t.translate(COMILLAS)
    t = t.replace('\u00a0', ' ').replace('\u2013', '-').replace('\u2014', '-')
    return re.sub(r'\s+', ' ', t).strip()


def sin_tildes(t: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', t)
                   if unicodedata.category(c) != 'Mn').lower()


# --------------------------------------------------------------------------
# Escalas
# --------------------------------------------------------------------------
LARGO = ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-',
         'BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-',
         'B+', 'B', 'B-', 'C', 'D', 'E']
CORTO = ['N1+', 'N1', 'N2', 'N3', 'N4', 'N5']
ACCIONES = ['1a Clase Nivel 1', '1a Clase Nivel 2', '1a Clase Nivel 3',
            '1a Clase Nivel 4', '2a Clase Nivel 5']

# Orden importa: los tokens largos primero para que "AA+" no matchee como "A".
_TOK_LARGO = r'(?:AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C|D|E)'
_TOK_CORTO = r'(?:N-?1\+|N-?[1-5])'
_TOK_FONDO = r'(?:(?:AAA|AA\+|AA-|AA|A\+|A-|A|BBB)\s*fm(?:\s*/\s*M[1-7])?|M[1-7]|RV-[1-5])'
_TOK_ACC = r'(?:(?:Primera|1\s*[°ºa]?)\s*Clase\s*Nivel\s*[1-4]|(?:Segunda|2\s*[°ºa]?)\s*Clase(?:\s*Nivel\s*5)?)'

RATING = rf'(?:{_TOK_ACC}|{_TOK_FONDO}|{_TOK_CORTO}|{_TOK_LARGO})'
# Borde propio: \b no sirve porque "AA-" y "A+" terminan en caracter no-word.
# Sin esto, "AA-/Estable" se lee como "AA" y se pierde el modificador.
RB = r'(?![A-Za-z0-9+\-])'
DUAL = rf'({_TOK_CORTO}){RB}\s*/\s*({_TOK_LARGO}){RB}'

PERSPECTIVAS = {
    'estable': 'Estable', 'estables': 'Estable',
    'positiva': 'Positiva', 'positivas': 'Positiva',
    'negativa': 'Negativa', 'negativas': 'Negativa',
    'en observacion': 'En Observación', 'observacion': 'En Observación',
    'desarrollo': 'En Desarrollo', 'en desarrollo': 'En Desarrollo',
}

# --------------------------------------------------------------------------
# Verbos -> accion
# --------------------------------------------------------------------------
VERBOS = [
    (r'\b(sube|subio|aumenta|aumento|eleva|elevo|incrementa|mejora)\b', 'sube'),
    (r'\b(baja|bajo|disminuye|disminuyo|reduce|redujo|rebaja|rebajo|desciende)\b', 'baja'),
    (r'\b(ratifica|ratifico|mantiene|mantuvo|confirma|confirmo)\b', 'mantiene'),
    (r'\b(asigna|asigno|clasifica|clasifico|otorga|otorgo|comienza la clasificacion)\b', 'nueva'),
    (r'\b(retira|retiro|retirar|cancela)\b', 'retiro'),
]


def escala_de(nota: str) -> str:
    if not nota:
        return 'largo'
    n = sin_tildes(nota)
    if 'clase' in n:
        return 'acciones'
    if re.fullmatch(r'n-?[1-5]\+?', n):
        return 'corto'
    if 'fm' in n or n.startswith('m') or n.startswith('rv'):
        return 'fondo'
    return 'largo'


def canon(nota: str) -> str:
    """Deja la nota en una forma comparable entre agencias."""
    if not nota:
        return ''
    n = normalizar(nota).strip(' ."\'')
    n = re.sub(r'^categor[ií]a\s+', '', n, flags=re.I)
    n = re.sub(r'^nivel\s+', '', n, flags=re.I)
    if re.search(r'clase', n, flags=re.I):
        m = re.search(r'nivel\s*([1-5])', n, flags=re.I)
        nivel = m.group(1) if m else '5'
        primera = bool(re.search(r'primera|\b1\b', n, flags=re.I))
        return f"{'1a' if primera else '2a'} Clase Nivel {nivel}"
    n = re.sub(r'^N-', 'N', n)          # N-1+ y N1+ son lo mismo
    n = re.sub(r'\s*/\s*', ' / ', n)
    return n.upper() if len(n) <= 4 and 'CLASE' not in n.upper() else n


def extraer_perspectiva(t: str):
    t2 = sin_tildes(t)
    m = re.search(r'(?:tendencia|perspectivas?)\D{0,30}?'
                  r'(estables?|positivas?|negativas?|en observacion|en desarrollo)', t2)
    if m:
        return PERSPECTIVAS.get(m.group(1))
    # formato "AA-/Estable"
    m = re.search(r'/\s*(estables?|positivas?|negativas?|en observacion)', t2)
    if m:
        return PERSPECTIVAS.get(m.group(1))
    return None


def _notas(t: str):
    """
    Devuelve (anterior, actual). Reglas de orden:
      "desde X hasta Y"  -> X anterior, Y actual
      "a X desde Y"      -> Y anterior, X actual
      una sola nota      -> actual
    """
    tn = normalizar(t)

    m = re.search(rf'desde\s+(?:categor[ií]a\s+)?({RATING}){RB}.*?'
                  rf'\b(?:hasta|a)\s+(?:categor[ií]a\s+)?({RATING}){RB}', tn, re.I)
    if m:
        return canon(m.group(1)), canon(m.group(2))

    m = re.search(rf'\ba\s+(?:categor[ií]a\s+)?({RATING}){RB}.*?'
                  rf'\bdesde\s+(?:categor[ií]a\s+)?({RATING}){RB}', tn, re.I)
    if m:
        return canon(m.group(2)), canon(m.group(1))

    # Rating dual corto/largo, ej. "N1+/AA+"
    m = re.search(DUAL, tn, re.I)
    if m:
        return None, f'{canon(m.group(1))} / {canon(m.group(2))}'

    m = re.search(rf'"\s*(?:categor[ií]a\s+)?({RATING}){RB}\s*"', tn, re.I)
    if m:
        return None, canon(m.group(1))

    m = re.search(rf'\b(?:en|a)\s+(?:categor[ií]a\s+)?({RATING}){RB}', tn, re.I)
    if m:
        return None, canon(m.group(1))

    m = re.search(rf'\b({RATING}){RB}\s*/', tn)
    if m:
        return None, canon(m.group(1))
    return None, None


def analizar(titular: str, emisor_conocido: str = None) -> dict:
    """
    Entrada: el titular tal cual lo publica la clasificadora.
    Salida: dict con accion, anterior, actual, perspectiva, escala.
    """
    t = normalizar(titular)
    tl = sin_tildes(t)

    accion = None
    for patron, etiqueta in VERBOS:
        if re.search(patron, tl):
            accion = etiqueta
            break

    anterior, actual = _notas(t)

    # "modifica" es ambiguo: puede ser nota o solo tendencia.
    if accion is None and re.search(r'\b(modifica|modifico|cambia|cambio)\b', tl):
        if anterior and actual:
            accion = 'sube' if _mejor(anterior, actual) else 'baja'
        else:
            accion = 'perspectiva'

    # Solo cambia la tendencia y no hay nota nueva
    if accion in (None, 'mantiene') and not actual and re.search(r'tendencia|perspectiva', tl):
        accion = 'perspectiva'

    # Si el verbo dice mantiene pero las notas difieren, gana la nota.
    if accion == 'mantiene' and anterior and actual and anterior != actual:
        accion = 'sube' if _mejor(anterior, actual) else 'baja'

    # Si el verbo dice sube/baja y solo hay una nota, es correcto igual:
    # la direccion viene del verbo aunque no sepamos la nota previa.

    return {
        'accion': accion or 'mantiene',
        'anterior': anterior,
        'actual': actual,
        'perspectiva': extraer_perspectiva(t),
        'escala': escala_de(actual or anterior),
        'titular': t,
        'emisor': emisor_conocido or extraer_emisor(t),
    }


def _mejor(anterior: str, actual: str) -> bool:
    """True si 'actual' es mejor nota que 'anterior'."""
    for esc in (LARGO, CORTO, ACCIONES):
        if anterior in esc and actual in esc:
            return esc.index(actual) < esc.index(anterior)
    return False


# --------------------------------------------------------------------------
# Emisor (heuristico, solo para fuentes que no lo entregan en campo aparte)
# --------------------------------------------------------------------------
# Clausulas que vienen DESPUES del emisor y hay que cortar antes de buscarlo.
_CORTES = re.compile(
    r'(?:,?\s+(?:y|e)\s+(?:en|clasifica|modifica|asigna|mantiene|ratifica|sus|la|las|los)\b'
    r'|,\s*(?:dado|debido|tras|manteniendo|modificando|desde|hasta|a la vez|as[ií] como)\b'
    r'|\.\s*(?:Las?\s+)?(?:perspectivas?|tendencia|sus|la serie|adicionalmente)\b'
    r'|\s+manteniendo\b|\s+modificando\b)', re.I)

# Palabras que nunca son el inicio de un nombre de emisor.
_RUIDO = re.compile(
    r'^(riesgo|clasificaci|solvencia|bonos|deuda|seguros?|categor|primera|segunda|nivel|'
    r'largo|corto|obligaciones|cuotas|acciones|t[ií]tulos|l[ií]neas?|efectos|dep[oó]sitos|'
    r'instrumentos|p[oó]lizas|fondos?)', re.I)

# Un tramo de nombre propio: arranca en mayuscula o digito y puede llevar
# conectores en minuscula intercalados (de, del, la, y...).
_NOMBRE = (r'(?:[A-ZÁÉÍÓÚÑ0-9][\wÁÉÍÓÚÑáéíóúñ&.\'’-]*)'
           r'(?:\s+(?:de|del|la|las|los|y|e|en|para)\b\s*'
           r'|\s+(?:[A-ZÁÉÍÓÚÑ0-9][\wÁÉÍÓÚÑáéíóúñ&.\'’-]*))*')

_TRAS_PREP = re.compile(rf'\b(?:de|para|a)\s+(?:la\s+|el\s+|los\s+|las\s+)?({_NOMBRE})\s*$')


def extraer_emisor(titular: str):
    """
    Devuelve el tramo final del titular que arranca justo despues de una
    preposicion y llega hasta el final. De los candidatos posibles toma el que
    empieza ANTES, porque "de Cristalerias de Chile S.A." es el emisor y
    "de Chile S.A." es solo su cola.

    Devuelve None si no logra algo limpio. El orquestador marca el registro
    para revision en vez de inventar un nombre.
    """
    t = normalizar(titular)
    t = _CORTES.split(t)[0]
    t = re.sub(r'[\s.,;:]+$', '', t)

    mejor = None
    for m in re.finditer(r'\b(?:de|para)\s+', t, re.I):
        resto = t[m.end():]
        resto = re.sub(r'^(?:la|el|los|las)\s+', '', resto, flags=re.I)
        if not resto or _RUIDO.match(sin_tildes(resto)):
            continue
        mm = re.match(rf'^({_NOMBRE})$', resto)
        if mm:
            mejor = mm.group(1).strip(' ,.')
            break          # el primero que llega al final es el bueno
    if mejor and len(mejor) > 2:
        return mejor
    return None
