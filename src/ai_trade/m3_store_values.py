"""Strict serialization at the new storage boundary; never cleans bad input."""
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit, parse_qsl

from ai_trade.storage.m3_schema import TABLES


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def stamp(value):
    if not isinstance(value,str): raise ValueError('timestamp must be text')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset() is None: raise ValueError('timezone required')
    return result.astimezone(timezone.utc).isoformat(timespec='microseconds')


def text(value):
    if (not isinstance(value,str) or not value or value!=value.strip() or len(value)>4096
            or any(ord(c)<32 or 127<=ord(c)<=159 for c in value)):
        raise ValueError('nonempty clean identifier/text required')
    if value.startswith(('https://','http://')):
        u=urlsplit(value)
        if u.username or u.password or any(k.lower() in {'token','key','api_key','secret','password'} for k,_ in parse_qsl(u.query)):
            raise ValueError('credential-bearing URL forbidden')
    return value


def _json_values(value):
    if value is None or type(value) is bool: return
    if type(value) is int:
        if not -(2**63)<=value<2**63: raise ValueError('JSON integer outside int64')
        return
    if type(value) is float:
        if not math.isfinite(value): raise ValueError('nonfinite JSON number')
        return
    if isinstance(value,str):
        if '\x00' in value: raise ValueError('NUL in JSON')
        return
    if isinstance(value,(list,tuple)):
        for v in value: _json_values(v)
        return
    if isinstance(value,dict):
        for k,v in value.items():
            if not isinstance(k,str) or k.lower() in {'password','api_key','authorization','cookie','proxy_password','access_token'}:
                raise ValueError('nontext or sensitive JSON key')
            _json_values(v)
        return
    raise ValueError('unsupported JSON scalar; no coercion')


def canonical(value):
    _json_values(value)
    result=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(result.encode())>2_000_000: raise ValueError('JSON exceeds 2MB boundary')
    return result


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(table, row):
    """Require exact fields, preserve NULL, reject bool/numeric string inputs."""
    spec=TABLES[table]; result={}
    if set(row)-set(spec.fields): raise ValueError(f'unknown fields for {table}: {set(row)-set(spec.fields)}')
    for item in spec.columns.split():
        key,kind=item.split(':'); nullable=kind.endswith('?'); kind=kind.rstrip('?')
        value=row.get(key)
        if value is None:
            if not nullable: raise ValueError(f'{table}.{key} required')
        elif kind=='t': value=text(value)
        elif kind in ('h','c'):
            if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(40 if kind=='c' else 64)+'}',value): raise ValueError(f'{key}: hex digest required')
        elif kind=='j': canonical(value)
        elif kind=='s': value=stamp(value)
        elif kind=='d':
            if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value: raise ValueError('canonical date required')
        elif kind in ('i','n','b'):
            if type(value) is not int or not -(2**63)<=value<2**63 or (kind=='n' and value<0) or (kind=='b' and value not in (0,1)): raise ValueError(f'{key}: exact bounded integer required')
        elif kind in ('f','p'):
            if type(value) not in (int,float): raise ValueError(f'{key}: numeric scalar required')
            try: converted=float(value)
            except (ValueError,OverflowError) as exc: raise ValueError('float conversion overflow') from exc
            if not math.isfinite(converted) or (value!=0 and converted==0) or (kind=='p' and converted<=0): raise ValueError(f'{key}: invalid finite number')
            value=converted
        result[key]=value
    return result


def insert(conn, table, row):
    row=fields(table,row)
    encoded={k:canonical(v) if k in {x.split(':')[0] for x in TABLES[table].columns.split() if x.split(':')[1].rstrip('?')=='j'} and v is not None else v for k,v in row.items()}
    conn.execute(f"INSERT INTO {table} ({','.join(encoded)}) VALUES ({','.join('?' for _ in encoded)})",tuple(encoded.values()))
    return row


def decoded(table, row):
    if row is None: raise ValueError(f'{table}: record missing')
    result=dict(row)
    for item in TABLES[table].columns.split():
        key,kind=item.split(':')
        if kind.rstrip('?')=='j' and result[key] is not None: result[key]=json.loads(result[key])
    return result


def one(conn, table, **keys):
    if table not in TABLES or not keys or set(keys)-set(TABLES[table].fields): raise ValueError('invalid query')
    return decoded(table,conn.execute(f"SELECT * FROM {table} WHERE "+' AND '.join(f'{k} IS ?' for k in keys),tuple(keys.values())).fetchone())


def rows(conn, table, **keys):
    if table not in TABLES or set(keys)-set(TABLES[table].fields): raise ValueError('invalid query')
    sql=f'SELECT * FROM {table}'
    if keys: sql+=' WHERE '+' AND '.join(f'{k} IS ?' for k in keys)
    return [decoded(table,r) for r in conn.execute(sql,tuple(keys.values()))]
