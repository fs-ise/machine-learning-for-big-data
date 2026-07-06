from __future__ import annotations
import ast

def _val(s):
    s=s.strip()
    if s in ('null','~'): return None
    if s in ('true','True'): return True
    if s in ('false','False'): return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return ast.literal_eval(s)
    if s.startswith('[') and s.endswith(']'):
        return ast.literal_eval(s)
    try: return int(s)
    except ValueError: return s

def safe_load(text):
    lines=[]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'): continue
        indent=len(raw)-len(raw.lstrip(' ')); lines.append((indent, raw.strip()))
    def parse_block(i, indent):
        if i>=len(lines): return {}, i
        is_list=lines[i][1] == '-' or lines[i][1].startswith('- ')
        out=[] if is_list else {}
        while i<len(lines) and lines[i][0]==indent:
            _, t=lines[i]
            if is_list:
                item=t[1:].strip()
                if not item:
                    val, i=parse_block(i+1, indent+2); out.append(val); continue
                if ':' in item:
                    k,v=item.split(':',1); d={k.strip(): _val(v) if v.strip() else None}; i+=1
                    if d[k.strip()] is None and i<len(lines) and lines[i][0]>indent:
                        d[k.strip()], i=parse_block(i, lines[i][0])
                    while i<len(lines) and lines[i][0]>indent:
                        subindent, subt=lines[i]
                        if subindent!=indent+2 or ':' not in subt: break
                        kk,vv=subt.split(':',1); kk=kk.strip()
                        if vv.strip(): d[kk]=_val(vv); i+=1
                        else: d[kk], i=parse_block(i+1, subindent+2)
                    out.append(d); continue
                out.append(_val(item)); i+=1
            else:
                if ':' not in t: i+=1; continue
                k,v=t.split(':',1); k=k.strip()
                if v.strip(): out[k]=_val(v); i+=1
                else: out[k], i=parse_block(i+1, indent+2)
        return out, i
    data,_=parse_block(0, lines[0][0] if lines else 0)
    return data

def safe_dump(data, sort_keys=False, allow_unicode=True):
    def emit(obj, indent=0):
        sp=' '*indent; out=[]
        if isinstance(obj, dict):
            items=obj.items() if not sort_keys else sorted(obj.items())
            for k,v in items:
                if isinstance(v,(dict,list)): out.append(f'{sp}{k}:'); out += emit(v, indent+2)
                else: out.append(f'{sp}{k}: {dump_val(v)}')
        elif isinstance(obj, list):
            for v in obj:
                if isinstance(v, dict):
                    out.append(f'{sp}-') ; out += emit(v, indent+2)
                else: out.append(f'{sp}- {dump_val(v)}')
        return out
    return '\n'.join(emit(data))+'\n'

def dump_val(v):
    if v is None: return 'null'
    if isinstance(v, str): return repr(v) if any(c in v for c in ':#[]{}') or v=='' else v
    return str(v).lower() if isinstance(v,bool) else str(v)
