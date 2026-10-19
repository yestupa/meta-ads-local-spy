"""通用小工具：JSON 读写、下载、域名、从 Facebook 页面里取内嵌 JSON。"""
import datetime
import json
import os
import re
import time
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except ValueError:
        return default


def stable_dumps(data, indent=None):
    """后台线程可能正在往数据里加字段，序列化结果偶尔会不完整：校验一遍，不对就重来。"""
    for i in range(8):
        try:
            s = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
            json.loads(s)
            return s
        except (RuntimeError, ValueError):
            if i == 7:
                raise
            time.sleep(0.05)


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    text = stable_dumps(data, indent=1)
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    # Windows 上目标文件正被别的程序读取（杀毒软件、同步盘等）时 os.replace 会“拒绝访问”，稍等重试
    for i in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.1 * (i + 1))


def opener(proxy=''):
    handlers = [urllib.request.ProxyHandler({'http': proxy, 'https': proxy})] if proxy else []
    return urllib.request.build_opener(*handlers)


def download(url, path, proxy='', timeout=90):
    """已存在且非空的文件直接跳过。"""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with opener(proxy).open(req, timeout=timeout) as r:
        data = r.read()
    with open(path + '.part', 'wb') as f:
        f.write(data)
    os.replace(path + '.part', path)
    return path


def fetch_json(url, proxy='', timeout=12):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with opener(proxy).open(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def host_of(url):
    m = re.match(r'(?:https?://)?([^/\s?#]+)', (url or '').strip())
    h = (m.group(1) if m else '').lower()
    return h[4:] if h.startswith('www.') else h


def registrable(host):
    """粗略取主域：shop.example.co.uk → example.co.uk"""
    parts = (host or '').split('.')
    if len(parts) >= 3 and parts[-2] in ('co', 'com', 'net', 'org', 'gov', 'ac') and len(parts[-1]) == 2:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:]) if len(parts) >= 2 else host


def ts_date(ts):
    return datetime.date.fromtimestamp(int(ts)) if ts else None


def walk(o, pred):
    """递归遍历 JSON，产出满足 pred 的 dict。"""
    if isinstance(o, dict):
        if pred(o):
            yield o
        for v in o.values():
            yield from walk(v, pred)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, pred)


def extract_json_objects_containing(text, key):
    """从页面脚本里取出包含 key 的最小平衡 JSON 对象（Facebook 把首屏数据内嵌在页面里）。"""
    out, pos = [], 0
    needle = f'"{key}"'
    while True:
        i = text.find(needle, pos)
        if i < 0:
            break
        st = text.rfind('{', 0, i)
        depth, j, in_str, esc = 0, st, False, False
        while j < len(text):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            out.append(json.loads(text[st:j + 1]))
        except ValueError:
            pass
        pos = j + 1
    return out


# 资源完整性自检（启动时运行）
_B = (
    ('YXBwL3dlYi9pbmRleC5odG1s', 'PGZvb3RlciBpZD0ieWVzdHVwYS13bSIgY2xhc3M9IndtIj5tYWRlIGJ5IDxhIGhyZWY9Imh0dHBzOi8veWVzdHVwYS5jb20iIHRhcmdldD0iX2JsYW5rIiByZWw9Im5vb3BlbmVyIj55ZXN0dXBhLmNvbTwvYT4vPGEgaHJlZj0iaHR0cHM6Ly95ZXN0dXBhLm5ldCIgdGFyZ2V0PSJfYmxhbmsiIHJlbD0ibm9vcGVuZXIiPnllc3R1cGEubmV0PC9hPiB3aXRoIOKdpO+4jzwvZm9vdGVyPg=='),
    ('YXBwL3dlYi9hcHAuanM=', 'Y29uc3QgV0FURVJNQVJLX0hUTUwgPSAnbWFkZSBieSA8YSBocmVmPSJodHRwczovL3llc3R1cGEuY29tIiB0YXJnZXQ9Il9ibGFuayIgcmVsPSJub29wZW5lciI+eWVzdHVwYS5jb208L2E+LzxhIGhyZWY9Imh0dHBzOi8veWVzdHVwYS5uZXQiIHRhcmdldD0iX2JsYW5rIiByZWw9Im5vb3BlbmVyIj55ZXN0dXBhLm5ldDwvYT4gd2l0aCDinaTvuI8nOwpjb25zdCBXQVRFUk1BUktfVEVYVCA9ICdtYWRlIGJ5IHllc3R1cGEuY29tL3llc3R1cGEubmV0IHdpdGgg4p2k77iPJzsKZnVuY3Rpb24gZW5zdXJlV2F0ZXJtYXJrKCkgewogIGxldCBmID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3llc3R1cGEtd20nKTsKICBpZiAoIWYgfHwgZi50ZXh0Q29udGVudC5yZXBsYWNlKC9ccysvZywgJyAnKS50cmltKCkgIT09IFdBVEVSTUFSS19URVhUIHx8IGdldENvbXB1dGVkU3R5bGUoZikuZGlzcGxheSA9PT0gJ25vbmUnIHx8IGdldENvbXB1dGVkU3R5bGUoZikudmlzaWJpbGl0eSA9PT0gJ2hpZGRlbicpIHsKICAgIGlmIChmKSBmLnJlbW92ZSgpOwogICAgZiA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2Zvb3RlcicpOwogICAgZi5pZCA9ICd5ZXN0dXBhLXdtJzsKICAgIGYuY2xhc3NOYW1lID0gJ3dtJzsKICAgIGYuaW5uZXJIVE1MID0gV0FURVJNQVJLX0hUTUw7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGYpOwogIH0KfQplbnN1cmVXYXRlcm1hcmsoKTsKbmV3IE11dGF0aW9uT2JzZXJ2ZXIoKCkgPT4gZW5zdXJlV2F0ZXJtYXJrKCkpLm9ic2VydmUoZG9jdW1lbnQuYm9keSwge2NoaWxkTGlzdDogdHJ1ZSwgc3VidHJlZTogdHJ1ZSwgYXR0cmlidXRlczogdHJ1ZSwgYXR0cmlidXRlRmlsdGVyOiBbJ3N0eWxlJywgJ2NsYXNzJywgJ2hpZGRlbiddfSk7CnNldEludGVydmFsKGVuc3VyZVdhdGVybWFyaywgMzAwMCk7'),
    ('YXBwL3dlYi9zdHlsZS5jc3M=', 'Lndte2Rpc3BsYXk6YmxvY2shaW1wb3J0YW50O3Zpc2liaWxpdHk6dmlzaWJsZSFpbXBvcnRhbnQ7b3BhY2l0eToxIWltcG9ydGFudDt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjIycHggMTZweCAyOHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTNweDtsZXR0ZXItc3BhY2luZzouMDJlbX0KLndtIGF7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtZGVjb3JhdGlvbjp1bmRlcmxpbmU7dGV4dC11bmRlcmxpbmUtb2Zmc2V0OjJweH0ud20gYTpob3Zlcntjb2xvcjp2YXIoLS1ibHVlKX0='),
    ('YXBwL21haW4ucHk=', 'V0FURVJNQVJLID0gKCc8Zm9vdGVyIGlkPSJ5ZXN0dXBhLXdtIiBjbGFzcz0id20iPm1hZGUgYnkgPGEgaHJlZj0iaHR0cHM6Ly95ZXN0dXBhLmNvbSIgdGFyZ2V0PSJfYmxhbmsiIHJlbD0ibm9vcGVuZXIiPnllc3R1cGEuY29tPC9hPi8nCiAgICAgICAgICAgICAnPGEgaHJlZj0iaHR0cHM6Ly95ZXN0dXBhLm5ldCIgdGFyZ2V0PSJfYmxhbmsiIHJlbD0ibm9vcGVuZXIiPnllc3R1cGEubmV0PC9hPiB3aXRoIOKdpO+4jzwvZm9vdGVyPicpCgoKZGVmIHdpdGhfd2F0ZXJtYXJrKGh0bWwpOgogICAgaWYgJ2lkPSJ5ZXN0dXBhLXdtIicgbm90IGluIGh0bWwgb3IgJ3llc3R1cGEuY29tJyBub3QgaW4gaHRtbDoKICAgICAgICBodG1sID0gaHRtbC5yZXBsYWNlKCc8L2JvZHk+JywgV0FURVJNQVJLICsgJ1xuPC9ib2R5PicpIGlmICc8L2JvZHk+JyBpbiBodG1sIGVsc2UgaHRtbCArIFdBVEVSTUFSSwogICAgcmV0dXJuIGh0bWw='),
    ('YXBwL21haW4ucHk=', 'Zi53cml0ZSh3aXRoX3dhdGVybWFyayhodG1sKSk='),
    ('YXBwL21haW4ucHk=', 'Ym9keSA9IHdpdGhfd2F0ZXJtYXJrKGYucmVhZCgpKS5lbmNvZGUoJ3V0Zi04Jyk='),
)
_C = (
    ('YXBwL3dlYi9zdHlsZS5jc3M=', 'eWVzdHVwYQ==', 0),
    ('YXBwL3dlYi9zdHlsZS5jc3M=', 'Lndt', 3),
    ('YXBwL3dlYi9pbmRleC5odG1s', 'eWVzdHVwYS13bQ==', 1),
    ('YXBwL3dlYi9hcHAuanM=', 'eWVzdHVwYS13bQ==', 2),
    ('YXBwL3dlYi9hcHAuanM=', 'V0FURVJNQVJL', 4),
    ('YXBwL21haW4ucHk=', 'Y2hlY2tfYnVuZGxlKCk=', 2),
    ('YXBwL2NvbmZpZy5weQ==', 'Y2hlY2tfYnVuZGxlKCk=', 1),
    ('YXBwL2pvYnMucHk=', 'Y2hlY2tfYnVuZGxlKCk=', 1),
)


def _bundle_ok():
    import base64 as _b
    d = lambda s: _b.b64decode(s).decode('utf-8')
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache = {}

    def rd(p):
        if p not in cache:
            try:
                with open(os.path.join(base, p), encoding='utf-8') as f:
                    cache[p] = f.read()
            except OSError:
                cache[p] = ''
        return cache[p]
    return all(d(f) in rd(d(p)) for p, f in _B) and all(rd(d(p)).count(d(k)) == n for p, k, n in _C)


def check_bundle():
    """程序文件不完整（作者署名被删改）时拒绝启动。"""
    if not _bundle_ok():
        print('程序文件不完整或已被修改（作者署名缺失），面板无法启动。\n请从原作者处重新下载完整版本：https://yestupa.com', flush=True)
        os._exit(1)
