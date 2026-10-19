"""Reference solution: recompute what each desk screen posted, from /app/data only.

The screens ran in MSHTML (the IE11 engine) inside a WebBrowser control. This file models the
submit handler in js/entry.js together with the behaviour of that engine in the document mode
each screen ends up in.
"""
import datetime
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP

DATA = '/app/data'
OUT = '/app/output/postback.json'

# ---------------------------------------------------------------- document mode
def screen_mode(html):
    """Mode MSHTML gives a page in a WebBrowser host without a FEATURE_BROWSER_EMULATION entry
    (IE7 emulation): an X-UA-Compatible meta counts only if it is the first one and no script
    element precedes it in the head; otherwise a page with a DOCTYPE gets IE7 mode."""
    head = html.split('</head>')[0]
    seen_script = False
    for name, attrs in re.findall(r'<(script|meta)\b([^>]*)>', head, re.I):
        if name.lower() == 'script':
            seen_script = True
        elif re.search(r'http-equiv\s*=\s*"X-UA-Compatible"', attrs, re.I):
            if seen_script:
                break
            content = re.search(r'content\s*=\s*"([^"]*)"', attrs).group(1)
            best = 0
            for v in re.split(r'[;,]', content):
                v = v.strip().lower()
                if v == 'ie=edge':
                    best = max(best, 11)
                elif re.fullmatch(r'ie=\d+', v):
                    best = max(best, int(v[3:]))
            return best
    return 7 if html.lstrip().upper().startswith('<!DOCTYPE') else 5


KEYED = {'ref': 'txtRef', 'party': 'txtParty', 'addr': 'txaAddr', 'inv_date': 'txtInvDate', 'arr_date': 'txtArrDate',
         'currency': 'selCurrency', 'freight': 'txtFreight', 'weight': 'txtWeight', 'pkgs': 'txtPkgs',
         'cntrs': 'txtCntrs', 'lines': 'txaLines'}


def shadowed_ids(html, mode):
    """Before IE8 mode, getElementById matches the name attribute as well as the id, ignoring case, and
    returns the first such element in document order. Keyed ids whose first match is another element
    (the validation anchors) read as undefined."""
    if mode >= 8:
        return set()
    out = set()
    tags = re.findall(r'<(\w+)([^>]*)>', html.split('<body', 1)[1])
    for cid in KEYED.values():
        for tag, attrs in tags:
            m_id = re.search(r'(?:^|\s)id="([^"]*)"', attrs)
            m_name = re.search(r'(?:^|\s)name="([^"]*)"', attrs)
            hit = [x.group(1).lower() for x in (m_id, m_name) if x]
            if cid.lower() in hit:
                if not (m_id and m_id.group(1) == cid):
                    out.add(cid)
                break
    return out


def json2_quote(s):
    """quote() of the shipped json2.js"""
    bs = chr(92)
    meta = {chr(8): bs + 'b', chr(9): bs + 't', chr(10): bs + 'n', chr(12): bs + 'f', chr(13): bs + 'r',
            '"': bs + '"', bs: bs + bs}

    def esc(ch):
        o = ord(ch)
        if ch in meta:
            return meta[ch]
        if (o < 0x20 or 0x7f <= o <= 0x9f or o == 0xad or 0x600 <= o <= 0x604 or o == 0x70f or o in (0x17b4, 0x17b5)
                or 0x200c <= o <= 0x200f or 0x2028 <= o <= 0x202f or 0x2060 <= o <= 0x206f or o == 0xfeff or o >= 0xfff0):
            return bs + 'u%04x' % o
        return ch
    return '"' + ''.join(esc(c) for c in s) + '"'


def native_quote(s):
    return json.dumps(s, ensure_ascii=False)


def to_locale_string(x, mode):
    """Number.prototype.toLocaleString for en-US: the Windows number format (two decimals) before IE9 mode,
    ECMA-402 (at most three decimals) in IE11 mode. The values here have at most one decimal."""
    if mode < 9:
        return '{:,.2f}'.format(Decimal(repr(x)))
    d = Decimal(repr(x))
    return '{:,}'.format(d) if d != d.to_integral_value() else '{:,}'.format(int(d))


# ---------------------------------------------------------------- white space and strings
# JScript in IE7/IE8 modes: \s and the String.trim fallback know only the ASCII blanks.
LEGACY_WS = '\t\n\x0b\x0c\r '
ES5_WS = LEGACY_WS + ''.join(chr(c) for c in (0xa0, 0x1680, 0x180e, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004,
                                               0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029,
                                               0x202f, 0x205f, 0x3000, 0xfeff))


def ws(mode):
    return LEGACY_WS if mode < 9 else ES5_WS


def js_trim(s, mode):
    return '' if s is None else s.strip(ws(mode))


def squash(s, mode):
    return re.sub('[%s]+' % re.escape(ws(mode)), ' ', js_trim(s, mode))


def js_split(s, pattern, mode):
    """split with a RegExp separator; IE7/IE8 modes leave every empty string out."""
    if s == '':
        return ['']
    parts = re.split(pattern, s)
    if mode < 9:
        parts = [p for p in parts if p != '']
    return parts


def js_upper(s):
    """Chakra uses simple one-to-one case mapping: sharp s and micro sign stay as they are."""
    out = []
    for ch in s:
        u = ch.upper()
        out.append(u if len(u) == 1 and ch != chr(0xb5) else ch)
    return ''.join(out)


# ---------------------------------------------------------------- numbers
def isnan(x):
    return x != x


def js_parse_int(s, mode):
    """parseInt without a radix; a leading 0 means octal in IE7/IE8 modes."""
    if s is None:
        return float('nan')
    s = s.lstrip(ES5_WS)
    sign = 1
    if s[:1] in ('+', '-') and s:
        sign = -1 if s[0] == '-' else 1
        s = s[1:]
    base = 10
    if s[:2] in ('0x', '0X'):
        base, s = 16, s[2:]
    elif mode < 9 and s[:1] == '0':
        base = 8
    digits = '0123456789abcdef'[:base]
    n = k = 0
    for ch in s:
        if ch.lower() not in digits:
            break
        n = n * base + digits.index(ch.lower())
        k += 1
    return sign * n if k else float('nan')


FLOAT_RE = re.compile(r'[+-]?(Infinity|(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)')


def js_parse_float(s):
    if s is None:
        return float('nan')
    m = FLOAT_RE.match(s.lstrip(ES5_WS))
    if not m:
        return float('nan')
    t = m.group(0)
    if 'Infinity' in t:
        return float('-inf') if t.startswith('-') else float('inf')
    return float(t)


def js_str(x):
    if isinstance(x, str):
        return x
    if isinstance(x, int):
        return str(x)
    if isnan(x):
        return 'NaN'
    if x == int(x) and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


def to_fixed(x, f):
    """Chakra's toFixed rounds half up on the shortest decimal form of the number."""
    if isnan(x):
        return 'NaN'
    d = Decimal(repr(float(x)))
    r = d.copy_abs().quantize(Decimal(1).scaleb(-f), rounding=ROUND_HALF_UP)
    return ('-' if d < 0 and r != 0 else '') + format(r, 'f')


def money(x):
    return '' if isnan(x) else to_fixed(x, 2)


def amount(s, mode):
    s = js_trim(s if s is not None else '', mode).replace(',', '')
    return 0 if s == '' else js_parse_float(s)


def or0(s):
    v = js_parse_float(s)
    return 0 if isnan(v) else v


# ---------------------------------------------------------------- dates
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
          'october', 'november', 'december']
WEEKDAY = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MON3 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
EPOCH = datetime.date(1970, 1, 1)


class JsDate:
    """local: the calendar date the getters return in US Eastern time; instant: days since the
    epoch in UTC, good to a few hours, which is all Math.round of a day difference needs."""

    def __init__(self, local, instant):
        self.local = local
        self.instant = instant


def local_date(y, mo, d):
    """Date(y, mo-1, d) with JavaScript's month and day overflow."""
    y += (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    return datetime.date(y, mo, 1) + datetime.timedelta(days=d - 1)


def at_local_midnight(day):
    return JsDate(day, (day - EPOCH).days + 5 / 24.0)


def ie_new_date(s, mode):
    """new Date(string) as JScript/Chakra parse the forms keyed at the desks."""
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        if mode < 9:
            return None                                  # no ISO dates before IE9 mode
        day = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return JsDate(day - datetime.timedelta(days=1), (day - EPOCH).days)   # UTC midnight
    m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{1,4})', s)
    if m:                                                # month/day/year, never range checked
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 1900
        return at_local_midnight(local_date(y, mo, d))
    mon, nums = None, []
    for t in [t for t in re.split(r'[\s,]+', s) if t]:
        if t.isdigit():
            nums.append(int(t))
        else:
            cands = [i for i, name in enumerate(MONTHS) if name.startswith(t.lower())]
            if len(t) < 2 or not cands:
                return None
            mon = cands[-1] + 1
    if mon is not None and len(nums) == 2:
        a, b = nums
        day, y = (a, b) if a <= 31 and b > 31 else (b, a)
        if y < 100:
            y += 1900
        return at_local_midnight(local_date(y, mon, day))
    return None


def parse_keyed_date(s, mode):
    s = js_trim(s, mode)
    if s == '':
        return None
    m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', s)
    if m:
        y = js_parse_int(m.group(3), mode)
        if y < 100:
            y += 2000
        return at_local_midnight(local_date(y, js_parse_int(m.group(2), mode), js_parse_int(m.group(1), mode)))
    return ie_new_date(s, mode)


def iso(d):
    return '' if d is None else '%d-%02d-%02d' % (d.local.year, d.local.month, d.local.day)


def to_date_string(d, mode):
    l = d.local
    day = ('%d' if mode < 9 else '%02d') % l.day
    return '%s %s %s %d' % (WEEKDAY[l.weekday()], MON3[l.month - 1], day, l.year)


WEEKDAY_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
LRM = chr(0x200e)


def to_locale_date_string(d, mode):
    """Before IE9 mode JScript formats with the Windows long date format of the user locale (en-US:
    dddd, MMMM d, yyyy). IE11 mode formats through ECMA-402 on Windows.Globalization, which wraps
    every field of the en-US short date in left-to-right marks."""
    l = d.local
    if mode < 9:
        return '%s, %s %d, %d' % (WEEKDAY_LONG[l.weekday()], MONTHS[l.month - 1].capitalize(), l.day, l.year)
    return '%s%d%s/%s%d%s/%s%d' % (LRM, l.month, LRM, LRM, l.day, LRM, LRM, l.year)


def get_year(d, mode):
    """Annex B getYear: JScript gives the full year outside 1900-1999; ES5 (IE9 mode on) always year - 1900."""
    y = d.local.year
    return y - 1900 if mode >= 9 or 1900 <= y <= 1999 else y


# ---------------------------------------------------------------- the submit handler
LETTER = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27,
                                                  28, 29, 30, 31, 32, 34, 35, 36, 37, 38]))


def container_ok(c, mode):
    if not re.fullmatch(r'[A-Z]{4}[0-9]{7}', c):
        return False
    if mode < 8:
        return False                                     # c[i] is undefined in IE7 mode
    s = sum((LETTER[ch] if i < 4 else int(ch)) * 2 ** i for i, ch in enumerate(c[:10]))
    return (s % 11) % 10 == int(c[10])


def hs_format(dg):
    if len(dg) < 6:
        return dg
    return dg[:4] + '.' + dg[4:6] + ('.' + dg[6:] if len(dg) > 6 else '')


def duty_rate(cell, hs, mode, tariff):
    r = js_trim(cell if cell is not None else '', mode).replace('%', '', 1)
    r = tariff['standard'] if r == '' or isnan(js_parse_float(r)) else js_parse_float(r)
    chapter = js_parse_int(hs[:2], mode)
    if not isnan(chapter) and chapter in tariff['plantChapters']:
        r += tariff['plantLevy']
    return r


def kilos(s, mode):
    w = js_trim(s, mode).lower()
    n = js_parse_float(w.replace(',', ''))
    if isnan(n):
        return ''
    if 'lb' in w:
        n = n * 0.45359237
    return to_fixed(n, 1)


def fx(currency, d, rates):
    t = rates.get(currency)
    if t is None:
        return 1
    if d is not None:
        k = '%d-%02d' % (d.local.year, d.local.month)
        if k in t:
            return t[k]
    return t['fallback']


def submit(keyed, screen, mode, rates, tariff, shadow=()):
    P = {}
    g = lambda k: None if KEYED[k] in shadow else keyed.get(KEYED[k], '')
    ref = js_upper(squash(g('ref'), mode))
    P['ref'] = ref
    P['ref_seq'] = ref if mode < 9 else ref[-6:]        # substr(-6): negative start counts as 0 before IE9
    P['party'] = js_upper(squash(g('party'), mode))
    addr = js_split(g('addr'), r'\r\n|\n', mode)
    P['addr1'] = js_trim(addr[0], mode) if len(addr) > 0 else ''
    P['addr2'] = js_trim(addr[1], mode) if len(addr) > 1 else ''
    if len(addr) > 3:
        addr[2] = ', '.join(addr[2:])
    P['addr3'] = js_trim(addr[2], mode) if len(addr) > 2 else ''
    block = [x for x in (P['addr1'], P['addr2'], P['addr3']) if x != '']
    # a textarea's value: IE7/IE8 modes turn every LF the script writes into CR LF; IE11 mode reads LF
    P['addr_block'] = ('\r\n' if mode < 9 else '\n').join(block)
    inv = parse_keyed_date(g('inv_date'), mode)
    arr = parse_keyed_date(g('arr_date'), mode)
    P['inv_date'] = iso(inv)
    P['arr_date'] = iso(arr)
    P['transit_days'] = js_str(int(round(arr.instant - inv.instant))) if inv and arr else ''
    P['inv_year'] = js_str(get_year(inv, mode)) if inv else ''
    P['arr_long'] = to_locale_date_string(arr, mode) if arr else ''
    rate = fx(g('currency'), inv, rates)
    P['fx_rate'] = js_str(rate)
    n, goods, duty_fc, descs = 0, 0.0, 0.0, []
    for row in js_split(g('lines'), r'\r\n|\n', mode):
        if js_trim(row, mode) == '':
            continue
        cells = js_split(row, r'\t', mode)
        cell = lambda i: cells[i] if len(cells) > i else None
        hs = re.sub(r'[^0-9]', '', cells[0])
        qty = js_parse_int(cell(2), mode)
        price = amount(cell(3), mode)
        value = money(float('nan') if isnan(qty) else qty * price)
        duty = money(js_parse_float(value) * duty_rate(cell(4), hs, mode, tariff) / 100)
        goods += or0(value)
        duty_fc += or0(duty)
        n += 1
        descs.append(js_upper(squash(cell(1) or '', mode)))
        if n <= 6:
            P['l%d_hs' % n] = hs_format(hs)
            P['l%d_desc' % n] = js_upper(squash(cell(1) or '', mode))
            P['l%d_qty' % n] = '' if isnan(qty) else js_str(qty)
            P['l%d_value' % n] = value
            P['l%d_duty' % n] = duty
    for k in range(n + 1, 7):
        for f in ('hs', 'desc', 'qty', 'value', 'duty'):
            P['l%d_%s' % (k, f)] = ''
    P['line_count'] = js_str(n)
    quote = json2_quote if mode < 8 else native_quote       # IE7 mode has no JSON; json2.js comes in by conditional comment
    P['lines_json'] = '[' + ','.join(quote(d) for d in descs) + ']'
    P['goods_fc'] = money(goods)
    goods_usd = money(goods * rate)
    freight_usd = money(amount(g('freight'), mode) * rate)
    P['goods_usd'] = goods_usd
    P['freight_usd'] = freight_usd
    P['cif_usd'] = money(or0(goods_usd) + or0(freight_usd))
    P['duty_usd'] = '0.00' if screen == 'EX' else money(duty_fc * rate)
    P['gross_kg'] = kg = kilos(g('weight'), mode)
    P['kg_text'] = '' if kg == '' else to_locale_string(js_parse_float(kg), mode) + ' kg'
    P['pkgs'] = js_str(js_parse_int(js_trim(g('pkgs'), mode), mode))
    toks = js_split(js_upper(js_trim(g('cntrs'), mode)), '[%s,;/]+' % re.escape(ws(mode)), mode)
    lst = [t for t in toks if t]
    P['cntrs'] = json.dumps(lst, separators=(',', ':'), ensure_ascii=False)
    P['cntr_check'] = ''.join('Y' if container_ok(t, mode) else 'N' for t in lst)
    P['docket'] = '%s %s / %s / %d line(s)' % (screen, ref, to_date_string(inv, mode) if inv else 'no invoice date', n)
    return P


# ---------------------------------------------------------------- inputs
def load_rates(path):
    src = open(path, encoding='utf-8').read()
    rates = {}
    for cur, body in re.findall(r'(\w+): \{(.*?)\n    \}', src, re.S):
        rates[cur] = {k: float(v) for k, v in re.findall(r"'?([\w-]+)'?: ([0-9.]+)", body)}
    tariff = {
        'standard': float(re.search(r'standard: ([0-9.]+)', src).group(1)),
        'plantLevy': float(re.search(r'plantLevy: ([0-9.]+)', src).group(1)),
        'plantChapters': [int(x) for x in re.search(r'plantChapters: \[([^\]]*)\]', src).group(1).split(',')],
    }
    return rates, tariff


def screen_code(html):
    return re.search(r"CV\.entry\.submit\(this, '(\w+)'\)", html).group(1)


def main():
    rates, tariff = load_rates(os.path.join(DATA, 'client/js/rates.js'))
    screens = {}
    for f in os.listdir(os.path.join(DATA, 'client')):
        if f.endswith('.html'):
            html = open(os.path.join(DATA, 'client', f), encoding='utf-8').read()
            mode = screen_mode(html)
            screens[f] = (screen_code(html), mode, shadowed_ids(html, mode))
    entries = {}
    with open(os.path.join(DATA, 'journal.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            j = json.loads(line)
            code, mode, shadow = screens[j['screen']]
            entries[j['entry']] = submit(j['keyed'], code, mode, rates, tariff, shadow)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump({'entries': entries}, fh, ensure_ascii=False)
    os.replace(tmp, OUT)


if __name__ == '__main__':
    main()
