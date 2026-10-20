"""抓取任务：排队、逐步执行、记录每一步的状态和失败原因。任务数据保存在 data/jobs/<任务ID>/job.json。"""
import collections
import datetime
import glob
import os
import queue
import re
import shutil
import threading
import traceback

from . import config
from .i18n import T, set_lang
from .util import load_json, save_json

STEPS = [
    ('browser', '启动浏览器'),
    ('collect', '采集广告资料库'),
    ('shop', '落地页商品与价格'),
    ('media', '下载素材 · 分镜 · 转写'),
    ('local', '本地分析'),
    ('analysis', 'AI 分析'),
]


class Cancelled(Exception):
    pass


def _slug(s):
    return re.sub(r'[^0-9A-Za-z]+', '-', s).strip('-')[:30] or 'kw'


def split_keywords(s):
    return [k.strip() for k in re.split(r'[,，\n;；]+', s or '') if k.strip()][:5]


class Job:
    def __init__(self, data):
        self.data = data
        self.dir = os.path.join(config.JOBS, data['id'])
        self.lock = threading.Lock()
        self.cancel = False
        self.deleted = False

    @property
    def id(self):
        return self.data['id']

    def save(self):
        if self.deleted:  # 任务已被删除：后台线程收尾时不要再把文件夹写回来
            return
        with self.lock:
            save_json(os.path.join(self.dir, 'job.json'), self.data)

    def log(self, msg):
        line = datetime.datetime.now().strftime('%H:%M:%S ') + msg
        self.data.setdefault('log', []).append(line)
        self.data['log'] = self.data['log'][-400:]
        print(f'[{self.id}] {msg}', flush=True)
        self.save()

    def step(self, key, status=None, msg=None, count=None):
        st = self.data['steps'][key]
        if status:
            st['status'] = status
        if msg is not None:
            st['msg'] = msg
        if count is not None:
            st['count'] = count
        self.data['current'] = msg if status == 'running' else self.data.get('current')
        self.save()

    def notice(self, scope, message, level='warn'):
        self.data.setdefault('notices', []).append({'scope': scope, 'level': level, 'message': message})
        self.save()

    def check(self):
        if self.cancel:
            raise Cancelled()

    def ad(self, aid):
        return next((a for a in self.data['results'].get('ads', []) if a['id'] == aid), None)


class Manager:
    def __init__(self):
        config.ensure_dirs()
        self.q = queue.Queue()
        self.jobs = {}
        for p in glob.glob(os.path.join(config.JOBS, '*', 'job.json')):
            d = load_json(p)
            if d:
                if d.get('status') in ('queued', 'running'):
                    d['status'] = 'failed'
                    lg = (d.get('options') or {}).get('lang')
                    d.setdefault('notices', []).append({'scope': T('任务', lg), 'level': 'error', 'message': T('面板被关闭，任务中断。可以点“重新抓取”。', lg)})
                for a in d.get('results', {}).get('ads', []):
                    if a.get('aiStatus') in ('queued', 'running'):
                        a['aiStatus'] = None
                self.jobs[d['id']] = Job(d)
        threading.Thread(target=self._worker, daemon=True).start()

    # ---- 对外接口 ----
    def list(self):
        rows = []
        for j in self.jobs.values():
            d = j.data
            ads = d.get('results', {}).get('ads', [])
            rows.append({'id': d['id'], 'keyword': d['keyword'], 'status': d['status'], 'createdAt': d['createdAt'],
                         'country': d['options'].get('country'), 'mode': d['options'].get('mode', 'keyword'), 'ads': len(ads), 'starred': sum(1 for a in ads if a.get('starred'))})
        return sorted(rows, key=lambda r: r['createdAt'], reverse=True)

    def get(self, jid):
        j = self.jobs.get(jid)
        return j.data if j else None

    def create(self, keyword, options):
        s = config.load_settings()
        lang = 'en' if (options.get('lang') or s.get('lang')) == 'en' else 'zh'
        mode = 'brand' if options.get('mode') == 'brand' else 'keyword'
        kws = [keyword.strip()] if mode == 'brand' else split_keywords(keyword)
        now = datetime.datetime.now()
        jid = now.strftime('%Y%m%d-%H%M%S-') + _slug(kws[0])
        num = lambda k, d, lo, hi: max(lo, min(hi, int(options.get(k) if options.get(k) not in (None, '') else d)))
        opts = {'country': options.get('country') if options.get('country') in config.COUNTRIES else s['country'],
                'depth': options.get('depth') if options.get('depth') in ('quick', 'standard', 'deep') else s['depth'],
                'activeOnly': bool(options.get('activeOnly', True)),
                'maxVideos': num('maxVideos', s['max_videos'], 0, 80), 'maxImages': num('maxImages', s['max_images'], 0, 300),
                'aiTopN': num('aiTopN', s['ai_top_n'], 0, 40), 'analyze': bool(options.get('analyze', s['auto_analyze'])),
                'lang': lang, 'mode': mode, 'pageId': re.sub(r'\D', '', str(options.get('pageId') or '')) or None,
                'terms': split_keywords(options.get('terms') or '') if isinstance(options.get('terms'), str) else list(options.get('terms') or [])[:10]}
        data = {'id': jid, 'keyword': ', '.join(kws), 'keywords': kws, 'createdAt': now.isoformat(timespec='seconds'), 'status': 'queued',
                'options': opts, 'steps': {k: {'label': T(lab, lang), 'status': 'pending'} for k, lab in STEPS},
                'results': {}, 'notices': [], 'log': []}
        job = Job(data)
        os.makedirs(job.dir, exist_ok=True)
        job.save()
        self.jobs[jid] = job
        self.q.put((jid, 'full', None))
        return data

    def reanalyze(self, jid):
        j = self.jobs.get(jid)
        if not j or j.data['status'] in ('queued', 'running'):
            return None
        lg = j.data['options'].get('lang')
        j.data['status'] = 'queued'
        j.data['steps']['analysis'] = {'label': T('AI 分析', lg), 'status': 'pending'}
        j.data['notices'] = [n for n in j.data.get('notices', []) if n['scope'] not in ('AI 分析', 'AI analysis')]
        j.save()
        self.q.put((jid, 'analyze', None))
        return j.data

    def analyze_ad(self, jid, aid):
        """单条素材的 AI 拆解（视频没下载的先下载、做分镜和转写）。不改变任务状态，进度记在 ad.aiStatus。"""
        j = self.jobs.get(jid)
        a = j and j.ad(aid)
        if not a:
            return {'error': T('素材不存在')}
        if j.data['status'] in ('queued', 'running'):
            return {'error': T('任务正在运行，等它结束后再拆解单条素材')}
        if a.get('aiStatus') in ('queued', 'running'):
            return {'error': T('这条素材已经在排队了')}
        a['aiStatus'], a['aiMsg'] = 'queued', T('排队中', j.data['options'].get('lang'))
        j.save()
        self.q.put((jid, 'ad', aid))
        return {'ok': True}

    def star(self, jid, aid, on):
        j = self.jobs.get(jid)
        a = j and j.ad(aid)
        if not a:
            return False
        a['starred'] = bool(on)
        if on:
            a['starredAt'] = datetime.datetime.now().isoformat(timespec='seconds')
        j.save()
        return True

    def starred(self):
        out = []
        for j in self.jobs.values():
            for a in j.data.get('results', {}).get('ads', []):
                if a.get('starred'):
                    out.append(dict(a, jobId=j.id, jobKeyword=j.data['keyword']))
        return sorted(out, key=lambda a: a.get('starredAt') or '', reverse=True)

    def cancel(self, jid):
        j = self.jobs.get(jid)
        if j and j.data['status'] in ('queued', 'running'):
            j.cancel = True
            if j.data['status'] == 'queued':
                j.data['status'] = 'cancelled'
                j.save()
        return bool(j)

    def delete(self, jid):
        j = self.jobs.pop(jid, None)
        if j:
            j.cancel = True
            j.deleted = True
            shutil.rmtree(j.dir, ignore_errors=True)
        return bool(j)

    # ---- 执行 ----
    def _worker(self):
        while True:
            jid, mode, arg = self.q.get()
            job = self.jobs.get(jid)
            if not job or job.data['status'] == 'cancelled':
                continue
            set_lang(job.data['options'].get('lang'))  # 这个任务的提示文字、日志和 AI 输出都用任务创建时的语言
            if mode == 'ad':
                run_one(job, arg, config.load_settings())
                continue
            job.cancel = False
            job.data['status'] = 'running'
            job.data['startedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
            job.save()
            try:
                settings = config.load_settings()
                if mode == 'full':
                    run_collect(job, settings)
                run_analysis(job, settings, force=(mode == 'analyze'))
                job.data['status'] = 'done'
            except Cancelled:
                job.data['status'] = 'cancelled'
                job.log(T('任务已取消'))
            except Exception as e:
                job.data['status'] = 'failed'
                job.notice(T('任务'), T('任务出错：{e}', e=e), 'error')
                job.log(traceback.format_exc()[-1500:])
            job.data['finishedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
            job.data['current'] = None
            job.save()
            if job.deleted:
                shutil.rmtree(job.dir, ignore_errors=True)


def launch_browser(pw, settings):
    from .util import check_bundle
    check_bundle()
    kw = {'headless': not settings.get('show_browser')}
    if settings.get('proxy'):
        kw['proxy'] = {'server': settings['proxy']}
    errors = []
    for ch in (None, 'chrome', 'msedge'):
        try:
            b = pw.chromium.launch(channel=ch, **kw) if ch else pw.chromium.launch(**kw)
            return b, {None: T('内置 Chromium'), 'chrome': 'Google Chrome', 'msedge': 'Microsoft Edge'}[ch]
        except Exception as e:
            errors.append(f'{ch or "chromium"}: {str(e).splitlines()[0][:140]}')
    raise RuntimeError(T('无法启动浏览器。请先运行“1-安装”，或安装 Google Chrome。详情：{d}', d=' ; '.join(errors)))


def run_collect(job, settings):
    from playwright.sync_api import sync_playwright

    from . import insights, media, meta, shop

    opts, res = job.data['options'], job.data['results']
    s = dict(settings, max_videos=opts['maxVideos'], max_images=opts['maxImages'])
    run_date = datetime.date.today()
    with sync_playwright() as pw:
        job.step('browser', 'running', T('正在启动浏览器'))
        try:
            browser, name = launch_browser(pw, settings)
        except Exception as e:
            job.step('browser', 'failed', str(e))
            for k in ('collect', 'shop', 'media', 'local'):
                job.step(k, 'skipped', T('浏览器没有启动'))
            raise RuntimeError(str(e))
        job.step('browser', 'done', T('已启动 {name}', name=name))
        try:
            ctx = browser.new_context(locale='en-US', viewport={'width': 1280, 'height': 1600},
                                      user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
            page = ctx.new_page()
            job.step('collect', 'running', T('正在打开 Meta 广告资料库'))
            prog = lambda m: job.step('collect', 'running', m)
            try:
                if opts.get('mode') == 'brand':
                    got = collect_brand(job, page, opts, prog)
                    if got is None:
                        return
                else:
                    got = meta.collect(page, job.data['keywords'], opts['country'], opts['depth'], opts['activeOnly'], job.log, prog, job.check)
            except meta.MetaError as e:
                job.step('collect', 'failed', str(e))
                job.notice(T('广告资料库'), str(e), 'error')
                for k in ('shop', 'media', 'local'):
                    job.step(k, 'skipped', T('没有采集到广告'))
                return
            ads = got['ads']
            res.update(ads=ads, queries=got['queries'], totals=got['totals'])
            tot = T('；').join(T('“{k}” 在投 {v} 条', k=k, v=f'{v:,}') for k, v in got['totals'].items() if v is not None)
            job.step('collect', 'done' if ads else 'failed', T('合并去重后 {n} 条广告', n=len(ads)) + (T('（资料库：{tot}）', tot=tot) if tot else ''), len(ads))
            if not ads:
                job.notice(T('广告资料库'), T('这个关键词在所选国家没有在投广告。换一个更宽泛的英文词，或者把国家改成“全部国家”再试。'))
                for k in ('shop', 'media', 'local'):
                    job.step(k, 'skipped', T('没有采集到广告'))
                return
            if got.get('stoppedEarly'):
                job.notice(T('广告资料库'), T('连续几次查询没有返回广告，可能被 Meta 暂时限流，已提前结束采集。过一会儿再试，或换一个代理节点。'))
            if opts.get('mode') == 'brand':
                pt = got['totals'].get(job.data['keyword'])
                if pt and pt > len(ads):
                    job.notice(T('广告资料库'), T('这个主页在投 {pt} 条，本次拿到 {n} 条（{pct}）。未登录时 Meta 每次只返回 30 条、翻页被限流，工具用多组排序/形式/平台组合和“主页内搜索”滚雪球来多拿素材。想要更多：选“深度”，或在“主页内关键词”里填品类词（如 dog food, cat litter）。',
                                                  pt=f'{pt:,}', n=len(ads), pct=f'{len(ads) / pt:.0%}'), 'info')
            elif any(v and v > len(ads) for v in got['totals'].values()):
                job.notice(T('广告资料库'), T('未登录时 Meta 每次只返回 30 条（翻页接口会被限流），所以工具用多组排序/筛选组合来多拿素材。想要更多，可以在“采集深度”里选“深度”，或者再加几个相关关键词（用逗号分隔）。'), 'info')
            job.save()
            job.check()

            # ---- 落地页商品（用同一个浏览器读取，Shopify 会拦截非浏览器的请求） ----
            if settings.get('shop_enrich'):
                job.step('shop', 'running', T('正在读取落地页商品信息'))
                try:
                    prods = shop.enrich(page, ads, job.log, lambda m: job.step('shop', 'running', m), job.check)
                    n_pages = sum(1 for a in ads if a.get('productKey'))
                    job.step('shop', 'done', T('{n} 条广告落地到商品页，读到 {p} 个 Shopify 商品的售价/原价', n=n_pages, p=len(prods)), len(prods))
                except Cancelled:
                    raise
                except Exception as e:
                    job.step('shop', 'failed', T('读取失败：{e}', e=str(e)[:150]))
            else:
                for a in ads:
                    a['domain'] = shop.product_ref(a.get('linkUrl'))[0]
                job.step('shop', 'skipped', T('设置里关闭了'))
        finally:
            try:
                browser.close()
            except Exception:
                pass
    job.check()

    # ---- 先打分排序，再按顺序下载素材 ----
    res['insights'] = insights.aggregate(ads, run_date)
    job.save()
    if not media.has_ffmpeg():
        job.notice(T('素材'), T('没有找到 ffmpeg（imageio-ffmpeg），视频无法分镜。请重新运行“1-安装”。'), 'error')
    if settings.get('transcribe') and not media.whisper_ok():
        job.notice(T('语音转写'), T('没有安装 faster-whisper，视频不做语音转写。需要的话运行“1-安装”时选择安装语音转写。'), 'info')
    job.step('media', 'running', T('正在下载素材'))
    n_v, n_i, fails = media.localize(ads, job.dir, s, job.log, lambda m: job.step('media', 'running', m), job.check)
    tpl = '视频 {v} 条（分镜、切镜节奏、语音转写），图片广告 {i} 条，缩略图 {t} 张' if settings.get('transcribe') and media.whisper_ok() else '视频 {v} 条（分镜、切镜节奏），图片广告 {i} 条，缩略图 {t} 张'
    job.step('media', 'done', T(tpl, v=n_v, i=n_i, t=sum(1 for a in ads if a.get('thumb'))) + (T('；{f} 条失败', f=fails) if fails else ''), n_v + n_i)
    job.check()

    # ---- 本地分析 ----
    job.step('local', 'running', T('正在统计'))
    res['insights'] = insights.media_aggregate(ads, insights.aggregate(ads, run_date))
    ins = res['insights']
    job.step('local', 'done', T('{a} 个店铺主页 · {p} 个落地商品 · {s} 组同款竞争 · {e} 条常青爆款', a=len(ins['advertisers']), p=len(ins['products']),
                                s=len(ins['sameProduct']), e=ins['verdicts'].get('常青爆款', 0)))
    job.save()


def collect_brand(job, page, opts, prog):
    """品牌模式：先识别官方主页（或用指定的主页 ID），再只抓这个主页的广告。返回与 meta.collect 相同结构；识别失败返回 None。"""
    from . import brand
    res = job.data['results']
    text = job.data['keyword']
    if opts.get('pageId'):
        best, cands = {'pageId': opts['pageId'], 'pageName': None, 'score': 100, 'reasons': [T('手动选择的主页')]}, []
    else:
        best, cands = brand.identify(page, text, opts['country'], job.log, prog)
    if not best:
        job.step('collect', 'failed', T('资料库里没有找到“{t}”相关的广告主页', t=text))
        job.notice(T('品牌主页'), T('按“{t}”搜索没有找到任何广告主页。试试品牌的英文名、官网域名（如 chewy.com）或 Facebook 主页链接。', t=text), 'error')
        for k in ('shop', 'media', 'local'):
            job.step(k, 'skipped', T('没有识别到主页'))
        return None
    res['brand'] = {'input': text, 'page': best, 'candidates': cands}
    job.save()
    if cands and (best['score'] < 45 or (len(cands) > 1 and cands[1]['score'] >= best['score'] - 5)):
        job.notice(T('品牌主页'), T('自动选择了“{n}”，但把握不大。请在“品牌主页”里核对，不对的话点候选主页旁的“改抓这个主页”。', n=best['pageName']))
    got = brand.collect(page, best['pageId'], text, opts['country'], opts['depth'], opts['activeOnly'], opts.get('terms') or [],
                        job.log, prog, job.check)
    if got['ads']:
        a0 = got['ads'][0]
        best.update(pageName=best.get('pageName') or a0.get('pageName'), pageUrl=best.get('pageUrl') or a0.get('pageUrl'),
                    likes=best.get('likes') or a0.get('pageLikes'), avatar=best.get('avatar') or a0.get('pageAvatar'))
    best['pageTotal'] = got['pageTotal']
    return {'ads': got['ads'], 'queries': got['queries'], 'totals': {text: got['pageTotal']}, 'stoppedEarly': False}


FATAL = ('无效', '连不上', '没有登录', '额度', '没有找到 Claude Code', '无法运行 Claude Code')


def _engine(job, settings):
    from .analyze import Analyzer, ClaudeCodeAnalyzer
    engine = settings.get('engine') or 'claude_code'
    return ClaudeCodeAnalyzer(settings, job.dir) if engine == 'claude_code' else Analyzer(settings)


def _norm(t):
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:400]


def run_analysis(job, settings, force=False):
    from .analyze import AnalyzeError

    opts, res = job.data['options'], job.data['results']
    ads = res.get('ads') or []
    kw = job.data['keyword']
    engine = settings.get('engine') or 'claude_code'
    if not ads:
        job.step('analysis', 'skipped', T('没有素材可分析'))
        return
    if not force and not opts.get('analyze'):
        job.step('analysis', 'skipped', T('本次任务没有勾选“抓完自动 AI 分析”，可以稍后点“AI 分析”'))
        return
    if engine == 'none':
        job.step('analysis', 'skipped', T('设置里选择了“不做 AI 分析”'))
        return
    if engine == 'api' and not settings.get('api_key'):
        job.step('analysis', 'skipped', T('未配置 Claude API key，跳过 AI 分析'))
        job.notice(T('AI 分析'), T('分析引擎选的是 Claude API，但没有填 API key。可以在“设置”里填 key，或者改成 Claude Code（用订阅，不需要 key），然后点“AI 分析”。'))
        return
    try:
        an = _engine(job, settings)
    except AnalyzeError as e:
        job.step('analysis', 'failed', str(e))
        job.notice(T('AI 分析'), str(e), 'error')
        return
    job.log(T('分析引擎：{e}（{m}）', e='Claude Code' if engine == 'claude_code' else 'Claude API', m=an.model))
    errors = []

    def attempt(label, fn):
        job.check()
        job.step('analysis', 'running', T('正在分析：{l}', l=label))
        try:
            return fn()
        except AnalyzeError as e:
            errors.append(T('{l}：{e}', l=label, e=e))
            job.log(T('分析失败 {l}：{e}', l=label, e=e))
            if getattr(e, 'fatal', False) or any(k in str(e) for k in FATAL):
                raise
        return None

    try:
        # 1. 文案：全部广告，同一段文案只分析一次
        groups = collections.OrderedDict()
        for a in ads:
            if a.get('body') and not a.get('copyReview'):
                groups.setdefault(_norm(a['body']), []).append(a)
        reps = [xs[0] for xs in groups.values()]
        for i in range(0, len(reps), 40):
            part = reps[i:i + 40]
            r = attempt(T('文案 {a}–{b} / {n} 段', a=i + 1, b=i + len(part), n=len(reps)), lambda part=part: an.copy_batch(kw, part)) or {}
            for rep in part:
                if rep['id'] in r:
                    for a in groups[_norm(rep['body'])]:
                        a['copyReview'] = r[rep['id']]
            job.save()
        # 2. 图片 / 视频：爆款指数前 N 条深度拆解
        top = [a for a in ads[:opts.get('aiTopN', 12)] if not a.get('analysis')]
        imgs = [a for a in top if not a.get('videos') and (a.get('localImages') or a.get('thumb'))]
        if imgs:
            r = attempt(T('图片素材（{n} 条）', n=len(imgs)), lambda: an.image_ads(kw, imgs, job.dir)) or {}
            for a in imgs:
                if a['id'] in r:
                    a['analysis'] = dict(r[a['id']], kind='image')
            job.save()
        for a in [a for a in top if a.get('videos')]:
            if not (a.get('video') or {}).get('storyboard') and not a.get('thumb'):
                continue
            out = attempt(T('视频 #{r} {p}', r=a['rank'], p=a.get('pageName') or ''), lambda a=a: an.video_ad(kw, a, job.dir))
            if out:
                a['analysis'] = dict(out, kind='video')
                job.save()
        # 3. 总结
        s = attempt(T('关键词总结'), lambda: an.summary(job.data))
        if s:
            res['summary'] = s
    except AnalyzeError as e:
        job.step('analysis', 'failed', str(e))
        job.notice(T('AI 分析'), str(e), 'error')
        return
    job.data['usage'] = an.usage
    msg = T('完成 {c} 次调用（输入约 {i} tokens，输出约 {o} tokens）', c=an.usage['calls'], i=f'{an.usage["input"]:,}', o=f'{an.usage["output"]:,}')
    job.step('analysis', 'done', msg + (T('；{n} 项失败', n=len(errors)) if errors else ''))
    for e in errors:
        job.notice(T('AI 分析'), e)


def run_one(job, aid, settings):
    """单条素材拆解：缺视频就先下载处理，然后图片/视频拆解 + 文案点评。"""
    from . import media
    from .analyze import AnalyzeError

    a = job.ad(aid)

    def upd(status, msg):
        a['aiStatus'], a['aiMsg'] = status, msg
        job.save()
    engine = settings.get('engine') or 'claude_code'
    if engine == 'none':
        return upd('failed', T('设置里的分析引擎是“不做 AI 分析”'))
    if engine == 'api' and not settings.get('api_key'):
        return upd('failed', T('分析引擎是 Claude API，但没有填 API key'))
    try:
        if a.get('videos') and not a.get('localVideo'):
            upd('running', T('正在下载视频、生成分镜、语音转写' if settings.get('transcribe') and media.whisper_ok() else '正在下载视频、生成分镜'))
            from .util import download
            v0 = a['videos'][0]
            p = download(v0.get('hd') or v0.get('sd'), os.path.join(job.dir, 'assets', 'media', f'{aid}.mp4'), settings.get('proxy') or '', 120)
            a['localVideo'] = f'assets/media/{aid}.mp4'
            a['video'] = media.process_video(p, os.path.join(job.dir, 'assets', 'media'), 'assets/media', aid,
                                             settings.get('transcribe') and media.whisper_ok(), settings.get('whisper_model', 'small'))
        elif not a.get('videos') and a.get('images') and not a.get('localImages'):
            from .util import download
            imgs = []
            for k, u in enumerate(a['images'][:6]):
                download(u, os.path.join(job.dir, 'assets', 'media', f'{aid}-img{k + 1}.jpg'), settings.get('proxy') or '', 40)
                imgs.append(f'assets/media/{aid}-img{k + 1}.jpg')
            a['localImages'] = imgs
        upd('running', T('正在用 AI 拆解（通常 1–3 分钟）'))
        an = _engine(job, settings)
        kw = job.data['keyword']
        if a.get('videos'):
            a['analysis'] = dict(an.video_ad(kw, a, job.dir), kind='video')
        else:
            a['analysis'] = dict(an.image_ads(kw, [a], job.dir)[aid], kind='image')
        if a.get('body') and not a.get('copyReview'):
            a['copyReview'] = an.copy_batch(kw, [a]).get(aid)
        upd('done', T('已拆解（{n} 次调用）', n=an.usage['calls']))
    except (AnalyzeError, KeyError) as e:
        upd('failed', (str(e) if isinstance(e, AnalyzeError) else '') or T('模型没有返回这条素材的结果'))
    except Exception as e:
        job.log(traceback.format_exc()[-1500:])
        upd('failed', T('拆解失败：{e}', e=str(e)[:200]))
