import json, urllib.request
URL = 'https://shijian-v2-jisu.aws-ap-northeast-1.turso.io/v2/pipeline'
TOK = open('/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/.secrets/turso-v2-full').read().strip()
def arg(v):
    if v is None: return {'type': 'null'}
    if isinstance(v, int): return {'type': 'integer', 'value': str(v)}
    return {'type': 'text', 'value': str(v)}
def run(stmts):
    reqs = [{'type': 'execute', 'stmt': {'sql': s, 'args': [arg(a) for a in (p or [])]}} for s, p in stmts] + [{'type': 'close'}]
    r = urllib.request.Request(URL, json.dumps({'requests': reqs}).encode(), {'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'})
    out = json.load(urllib.request.urlopen(r, timeout=120))['results']
    res = []
    for o in out[:-1]:
        if o['type'] != 'ok': raise RuntimeError(o)
        rr = o['response']['result']; cols = [c['name'] for c in rr['cols']]
        res.append([dict(zip(cols, [c.get('value') for c in row])) for row in rr['rows']])
    return res
def q(sql, *p): return run([(sql, list(p))])[0]
