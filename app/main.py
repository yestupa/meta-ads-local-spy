"""本地面板服务：python -m app.main 启动后，浏览器打开 http://127.0.0.1:8766 。只监听本机，不对外开放。"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config
from .i18n import T, get_lang, set_lang
from .jobs import Manager
from .util import stable_dumps

PORT = int(os.environ.get('METASPY_PORT', '8766'))
manager = None


def env_check():
    """返回检查项列表。key 固定不变（tools/setup.py 按 key 判断），name/detail 按当前语言显示。"""
    s = config.load_settings()
    out = []

    def add(key, name, ok, detail):
        out.append({'key': key, 'name': name, 'ok': ok, 'detail': detail})
    add('python', 'Python', sys.version_info >= (3, 10), sys.version.split()[0])
    try:
        import playwright  # noqa
        add('playwright', 'Playwright', True, T('已安装'))
    except ImportError:
        add('playwright', 'Playwright', False, T('未安装，请先运行“1-安装”'))
    from . import media
    add('ffmpeg', T('ffmpeg（视频分镜）'), media.has_ffmpeg(), T('已安装') if media.has_ffmpeg() else T('未安装，请重新运行“1-安装”'))
    w = media.whisper_ok()
    add('whisper', T('语音转写'), w or not s.get('transcribe'),
        T('已安装 faster-whisper（模型 {m}）', m=s.get('whisper_model', 'small')) if w else T('未安装 faster-whisper（不影响抓取，只是视频没有口播文字）'))
    from .analyze import system_proxy
    proxy = s.get('proxy') or system_proxy()
    fine = T('正常（代理 {p}）', p=proxy) if proxy else T('正常')
    try:
        h = [urllib.request.ProxyHandler({'http': proxy, 'https': proxy})] if proxy else []
        urllib.request.build_opener(*h).open(urllib.request.Request('https://www.facebook.com/ads/library/', headers={'User-Agent': 'Mozilla/5.0'}), timeout=10)
        add('facebook', T('访问 Facebook'), True, fine)
    except urllib.error.HTTPError:  # Facebook 对非浏览器请求返回 403/challenge，能收到响应就说明网络是通的
        add('facebook', T('访问 Facebook'), True, fine)
    except Exception as e:
        add('facebook', T('访问 Facebook'), False, T('失败：{e}。请开启代理/VPN，或在设置里填写代理地址', e=str(e)[:80]))
    engine = s.get('engine') or 'claude_code'
    if engine == 'claude_code':
        ok, detail = claude_status_cached()
        add('ai', T('AI 分析：Claude Code'), ok, detail + ('' if ok else T('（不影响抓取和本地分析）')))
    elif engine == 'api':
        add('ai', T('AI 分析：Claude API'), bool(s.get('api_key')), T('已填写 API key') if s.get('api_key') else T('未填写 API key（不影响抓取和本地分析）'))
    else:
        add('ai', T('AI 分析'), True, T('已关闭（只抓取 + 本地分析）'))
    return out


_cc_cache = {}


def claude_status_cached(force=False):
    """检查 Claude Code 登录状态会发一个极小的请求，所以结果按语言缓存 5 分钟。"""
    import time
    from .analyze import claude_cli_status
    lang = get_lang()
    c = _cc_cache.get(lang)
    if force or not c or time.time() - c[0] > 300:
        c = _cc_cache[lang] = (time.time(), claude_cli_status(settings=config.load_settings()))
    return c[1]


# 署名水印：作者要求保留，请勿删除或修改。页面里缺了会在这里补上。
WATERMARK = ('<footer id="yestupa-wm" class="wm">made by <a href="https://yestupa.com" target="_blank" rel="noopener">yestupa.com</a>/'
             '<a href="https://yestupa.net" target="_blank" rel="noopener">yestupa.net</a> with ❤️</footer>')


def with_watermark(html):
    if 'id="yestupa-wm"' not in html or 'yestupa.com' not in html:
        html = html.replace('</body>', WATERMARK + '\n</body>') if '</body>' in html else html + WATERMARK
    return html


def export_report(job):
    from .util import check_bundle
    check_bundle()
    web = config.WEB
    html = open(os.path.join(web, 'index.html'), encoding='utf-8').read()
    css = open(os.path.join(web, 'style.css'), encoding='utf-8').read()
    js = open(os.path.join(web, 'app.js'), encoding='utf-8').read()
    data = json.dumps(job, ensure_ascii=False).replace('</', '<\\/')
    html = html.replace('<link rel="stylesheet" href="/static/style.css">', f'<style>{css}</style>')
    html = html.replace('<script src="/static/app.js"></script>', f'<script>window.STATIC_JOB = {data};</script><script>{js}</script>')
    path = os.path.join(config.JOBS, job['id'], T('报告.html', job['options'].get('lang')))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(with_watermark(html))
    return path


def export_csv(job):
    """全部素材写成 CSV（UTF-8 带 BOM，Excel 能直接打开中文）。"""
    import csv
    j = lambda xs: ' | '.join(str(x) for x in (xs or []))
    an = lambda a: a.get('analysis') or {}
    cr = lambda a: a.get('copyReview') or {}
    lg = job['options'].get('lang')
    v = lambda x: T(x, lg) if isinstance(x, str) else x  # 判定、标签、开头类型等分类值
    cols = [
        ('排名', lambda a: a.get('rank')), ('爆款指数', lambda a: a.get('score')), ('判定', lambda a: v(a.get('verdict'))),
        ('资料库编号', lambda a: a['id']), ('资料库链接', lambda a: a.get('libraryUrl')), ('主页', lambda a: a.get('pageName')),
        ('主页粉丝', lambda a: a.get('pageLikes')), ('形式', lambda a: a.get('format')), ('上线日期', lambda a: a.get('startDate')),
        ('在投天数', lambda a: a.get('daysLive')), ('同素材广告数', lambda a: a.get('variants')), ('曝光排序位置', lambda a: a.get('impRank')),
        ('平台', lambda a: j(a.get('platforms'))), ('主文案', lambda a: a.get('body')), ('标题', lambda a: a.get('title')),
        ('链接描述', lambda a: a.get('linkDescription')), ('CTA', lambda a: a.get('cta')), ('落地页', lambda a: a.get('linkUrl')),
        ('域名', lambda a: a.get('domain')), ('商品名', lambda a: (a.get('product') or {}).get('title')),
        ('售价', lambda a: (a.get('product') or {}).get('price')), ('原价', lambda a: (a.get('product') or {}).get('compareAt')),
        ('文案标签', lambda a: j(v(t) for t in (a.get('copy') or {}).get('tags') or [])), ('开头类型', lambda a: v((a.get('copy') or {}).get('hookType'))),
        ('视频秒数', lambda a: (a.get('video') or {}).get('seconds')), ('镜头数', lambda a: (a.get('video') or {}).get('shots')),
        ('平均镜头时长', lambda a: (a.get('video') or {}).get('avgShot')), ('口播转写', lambda a: ((a.get('video') or {}).get('transcript') or {}).get('text')),
        ('AI 卖点角度', lambda a: cr(a).get('angle') or an(a).get('angle')), ('AI 钩子类型', lambda a: cr(a).get('hookType')),
        ('AI 文案结构', lambda a: cr(a).get('formula')), ('AI 文案分', lambda a: cr(a).get('score')), ('AI 文案点评', lambda a: cr(a).get('note')),
        ('AI 素材形式', lambda a: an(a).get('creativeType')), ('AI 钩子', lambda a: an(a).get('hook')),
        ('AI 优点', lambda a: j(an(a).get('strengths'))), ('AI 可改良', lambda a: j(an(a).get('improvements'))),
        ('AI 可借鉴', lambda a: an(a).get('borrow')), ('AI 改写', lambda a: an(a).get('rewrite')), ('收藏', lambda a: '★' if a.get('starred') else ''),
    ]
    path = os.path.join(config.JOBS, job['id'], T('素材清单.csv', lg))
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow([T(c[0], lg) for c in cols])
        for a in job.get('results', {}).get('ads', []):
            w.writerow(['' if c[1](a) is None else c[1](a) for c in cols])
    return path


def open_folder(path):
    if sys.platform.startswith('win'):
        os.startfile(path)  # noqa
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


class ExclusiveServer(ThreadingHTTPServer):
    """独占端口：Windows 上默认的地址复用会让两个面板同时监听同一端口。"""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        import socket
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = stable_dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        """支持 Range 请求，视频才能在面板里拖动进度条、点转写跳转。"""
        if not os.path.isfile(path):
            return self._json({'error': 'not found'}, 404)
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/javascript',):
            ctype += '; charset=utf-8'
        size = os.path.getsize(path)
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range') or '')
        start, end = 0, size - 1
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        try:
            with open(path, 'rb') as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except ValueError:
            return {}

    @staticmethod
    def _safe_join(base, rel):
        p = os.path.realpath(os.path.join(base, rel))
        return p if p.startswith(os.path.realpath(base) + os.sep) else None

    def do_GET(self):
        set_lang(config.load_settings().get('lang'))
        u = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(x) for x in u.path.strip('/').split('/') if x]
        if not parts:
            with open(os.path.join(config.WEB, 'index.html'), encoding='utf-8') as f:
                body = with_watermark(f.read()).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts[0] == 'static' and len(parts) == 2:
            p = self._safe_join(config.WEB, parts[1])
            return self._file(p) if p else self._json({'error': 'bad path'}, 400)
        if parts[0] == 'files' and len(parts) >= 3:
            p = self._safe_join(os.path.join(config.JOBS, parts[1]), '/'.join(parts[2:]))
            return self._file(p) if p else self._json({'error': 'bad path'}, 400)
        if parts[:2] == ['api', 'settings']:
            return self._json(config.public_settings())
        if parts[:2] == ['api', 'check']:
            if 'refresh=1' in (u.query or ''):
                _cc_cache['v'] = None
            return self._json(env_check())
        if parts[:2] == ['api', 'starred']:
            return self._json(manager.starred())
        if parts[:2] == ['api', 'jobs']:
            if len(parts) == 2:
                return self._json(manager.list())
            j = manager.get(parts[2])
            return self._json(j) if j else self._json({'error': T('任务不存在')}, 404)
        return self._json({'error': 'not found'}, 404)

    def do_POST(self):
        set_lang(config.load_settings().get('lang'))
        u = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(x) for x in u.path.strip('/').split('/') if x]
        body = self._body()
        if parts[:2] == ['api', 'settings']:
            config.save_settings(body)
            return self._json(config.public_settings())
        if parts[:2] == ['api', 'jobs'] and len(parts) == 2:
            kw = (body.get('keyword') or '').strip()
            if not kw:
                return self._json({'error': T('请输入关键词')}, 400)
            return self._json(manager.create(kw, body.get('options') or {}))
        if parts[:2] == ['api', 'jobs'] and len(parts) == 4:
            jid, action = parts[2], parts[3]
            j = manager.get(jid)
            if not j:
                return self._json({'error': T('任务不存在')}, 404)
            if action == 'analyze':
                r = manager.reanalyze(jid)
                return self._json(r or {'error': T('任务正在运行，稍后再试')}, 200 if r else 409)
            if action == 'analyzead':
                r = manager.analyze_ad(jid, str(body.get('adId') or ''))
                return self._json(r, 409 if r.get('error') else 200)
            if action == 'star':
                ok = manager.star(jid, str(body.get('adId') or ''), body.get('on'))
                return self._json({'ok': ok}, 200 if ok else 404)
            if action == 'cancel':
                manager.cancel(jid)
                return self._json({'ok': True})
            if action == 'delete':
                manager.delete(jid)
                return self._json({'ok': True})
            if action == 'rerun':
                opts = dict(j['options'])
                if body.get('pageId'):  # 品牌模式：改抓用户选的候选主页
                    opts['pageId'] = body['pageId']
                return self._json(manager.create(j['keyword'], opts))
            if action == 'export':
                p = export_report(j)
                open_folder(os.path.dirname(p))
                return self._json({'ok': True, 'path': p})
            if action == 'csv':
                p = export_csv(j)
                open_folder(os.path.dirname(p))
                return self._json({'ok': True, 'path': p})
            if action == 'open':
                open_folder(os.path.join(config.JOBS, jid))
                return self._json({'ok': True})
        return self._json({'error': 'not found'}, 404)


def main():
    global manager
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    from .util import check_bundle
    check_bundle()
    set_lang(config.load_settings().get('lang'))
    url = f'http://127.0.0.1:{PORT}'
    try:
        srv = ExclusiveServer(('127.0.0.1', PORT), Handler)
    except OSError:
        print(T('面板已经在运行（端口 {p} 被占用），直接打开：{u}', p=PORT, u=url), flush=True)
        if os.environ.get('METASPY_NO_BROWSER') != '1':
            webbrowser.open(url)
        return
    manager = Manager()
    print(T('面板已启动：{u}  （关闭这个窗口即可停止）', u=url), flush=True)
    if os.environ.get('METASPY_NO_BROWSER') != '1':
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
