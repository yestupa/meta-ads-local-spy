"""用 Claude 分析 Meta 广告素材（跨境电商视角）：
1. 文案：每条广告的卖点角度、钩子类型、文案结构、优惠、打分和一句话点评（纯文本，批量，覆盖全部广告）；
2. 图片：识别图中文字、画面、卖点，点评优点和可改良之处，给出可借鉴做法和英文改写；
3. 视频：看逐秒分镜 + 前 3 秒钩子帧 + 带时间戳的语音转写，拆逐镜头脚本，评价钩子、结构和节奏；
4. 关键词总结：产品与价格带、爆款打法、钩子/画面/视频套路、优惠策略、空白机会、3 个可直接拍的素材方案。

两种引擎：Claude Code（本机已登录的 claude 命令行，用订阅额度）或 Claude API（API key，按量付费）。
"""
import base64
import json
import os
import re
import subprocess
import urllib.request
from typing import List

from pydantic import BaseModel, Field

SYSTEM = ('你是资深的跨境电商 Meta（Facebook / Instagram）广告投放与素材策划顾问，帮助卖家研究竞对在投的广告素材，找到可以借鉴的爆款打法。'
          '只根据提供的文字、图片和数据下结论，不编造看不到的数据（点击率、转化率、花费、ROAS 等）。'
          '“在投天数”“同素材广告数”“曝光排序位置”是资料库公开的跑量信号，可以引用。'
          '用简体中文回答，具体、可执行；改写示例和广告文案保持广告原本的语言（通常是英文）。')

FALLBACK_MODELS = {'claude-opus-5-5', 'claude-sonnet-5-5'}


class CopyReview(BaseModel):
    id: str = Field(description='素材编号，原样返回')
    angle: str = Field(description='核心卖点/诉求角度，一句话')
    hookType: str = Field(description='开头钩子类型，2-6 个字，如 痛点提问 / 结果承诺 / 反常识 / 社会证明 / 优惠直给 / 故事开场')
    formula: str = Field(description='文案结构，如 痛点→方案→证明→优惠→CTA')
    offer: str = Field(description='优惠/价格信息；没有写 无')
    score: int = Field(description='文案力打分 1-10')
    note: str = Field(description='一句话点评：最值得学的地方或最大的问题')


class CopyBatch(BaseModel):
    reviews: List[CopyReview]


class CreativeReview(BaseModel):
    id: str = Field(description='素材编号，原样返回')
    product: str = Field(description='推广的是什么产品，一句话')
    angle: str = Field(description='核心卖点/诉求角度')
    hook: str = Field(description='首屏/首图钩子：第一眼看到什么、为什么会停下来')
    visual: str = Field(description='画面描述：主体、构图、场景、配色、文字排版、品牌露出')
    textInImage: str = Field(description='图中可读到的文字（OCR），没有写空字符串')
    creativeType: str = Field(description='素材形式，2-8 个字，如 产品白底图 / 场景生活图 / 前后对比 / 买家秀 / 图文卖点海报 / 轮播多卖点')
    audience: str = Field(description='推测的目标人群')
    strengths: List[str] = Field(description='优点 2-4 条，具体到哪个画面、哪句话')
    improvements: List[str] = Field(description='可改良的空间 2-4 条，每条给出具体改法')
    borrow: str = Field(description='我方可以直接借鉴的做法，具体可执行')
    rewrite: str = Field(description='改写后的广告主文案（保持原语言）')


class CreativeBatch(BaseModel):
    reviews: List[CreativeReview]


class Shot(BaseModel):
    time: str = Field(description='时间段，如 0–3s')
    visual: str = Field(description='画面内容（含字幕/贴字）')
    audio: str = Field(description='口播/音效/音乐；没有写空字符串')
    purpose: str = Field(description='这个镜头的作用')


class VideoReview(BaseModel):
    product: str
    creativeType: str = Field(description='视频形式，如 UGC 口播测评 / 产品演示 / 前后对比 / 开箱 / 问题-解决短剧 / 达人种草 / 图文快剪')
    hook: str = Field(description='前 3 秒钩子是什么（画面 + 字幕 + 口播），为什么有效或无效')
    structure: str = Field(description='整体脚本结构，如 痛点→产品→演示→证明→优惠→CTA')
    pace: str = Field(description='节奏评价（结合切镜数据）')
    script: List[Shot]
    angle: str
    audience: str
    strengths: List[str]
    improvements: List[str]
    borrow: str = Field(description='我方可以直接借鉴的做法')
    rewrite: str = Field(description='改良后的脚本思路（分镜级别，4-7 步，含前 3 秒钩子）')


class Signal(BaseModel):
    title: str
    body: str = Field(description='带证据：素材编号、店铺名、天数、价格等')


class Concept(BaseModel):
    name: str = Field(description='方案名（中文）')
    format: str = Field(description='素材形式和时长，如 9:16 UGC 口播 20 秒 / 1:1 轮播 4 张')
    angle: str
    hook: str = Field(description='前 3 秒钩子（画面 + 字幕/口播）')
    outline: List[str] = Field(description='分镜或每张图的内容，4-7 步')
    primaryText: str = Field(description='广告主文案（英文或目标市场语言）')
    headline: str = Field(description='广告标题（≤40 字符）')
    reference: str = Field(description='参考了哪些竞对素材（编号）')


class MarketSummary(BaseModel):
    overview: str = Field(description='这个关键词下的竞争格局，3-5 句：多少店铺在投、头部是谁、素材形式和投放时长')
    products: List[str] = Field(description='产品与价格带观察 2-5 条（有落地页价格数据时引用）')
    signals: List[Signal] = Field(description='关键发现 4-8 条')
    winningAngles: List[str] = Field(description='跑得最久/最靠前的素材用的卖点角度')
    hookPatterns: List[str] = Field(description='常见的开头钩子套路，附例句')
    visualPatterns: List[str] = Field(description='图片素材的画面套路')
    videoPatterns: List[str] = Field(description='视频素材的脚本和剪辑套路')
    offers: List[str] = Field(description='优惠与价格策略')
    opportunities: List[str] = Field(description='竞对没做好、我方可以切入的空白点')
    recommendations: List[str] = Field(description='给我方的 3-6 条具体素材建议')
    concepts: List[Concept] = Field(description='3 个可以直接拍/做的素材方案')


class AnalyzeError(RuntimeError):
    pass


def system_proxy():
    try:
        p = urllib.request.getproxies()
        return p.get('https') or p.get('http') or ''
    except Exception:
        return ''


def _metrics(a):
    m = {k: a.get(k) for k in ('id', 'pageName', 'format', 'daysLive', 'startDate', 'variants', 'impRank', 'platforms', 'score', 'verdict', 'cta')}
    m['landing'] = a.get('linkUrl')
    if a.get('product'):
        m['landingProduct'] = {k: a['product'].get(k) for k in ('title', 'price', 'compareAt')}
    return m


class Analyzer:
    def __init__(self, settings):
        import anthropic
        self.anthropic = anthropic
        self.settings = settings
        proxy = settings.get('proxy') or system_proxy()
        kw = {'api_key': settings['api_key'], 'max_retries': 3}
        if proxy:
            kw['http_client'] = anthropic.DefaultHttpxClient(proxy=proxy)
        self.client = anthropic.Anthropic(**kw)
        self.model = settings.get('model') or 'claude-sonnet-5-5'
        self.effort = settings.get('effort') or 'medium'
        self.usage = {'input': 0, 'output': 0, 'calls': 0}

    def _call(self, content, schema, max_tokens=16000):
        a = self.anthropic
        content = [self._b64(c['path']) if c.get('type') == 'image_path' else c for c in content]
        kw = dict(model=self.model, max_tokens=max_tokens, system=SYSTEM, messages=[{'role': 'user', 'content': content}],
                  output_config={'effort': self.effort}, output_format=schema)
        if self.model in FALLBACK_MODELS:
            kw.update(fallbacks='default', betas=['server-side-fallback-2026-07-01'])
        try:
            resp = self.client.beta.messages.parse(**kw)
        except a.AuthenticationError as e:
            raise AnalyzeError('API key 无效，请在“设置”里检查') from e
        except a.PermissionDeniedError as e:
            raise AnalyzeError(f'API key 没有权限：{e.message}') from e
        except a.NotFoundError as e:
            raise AnalyzeError(f'模型不存在或不可用：{self.model}') from e
        except a.RateLimitError as e:
            raise AnalyzeError('API 调用太频繁或额度不足（429），请稍后再试') from e
        except a.BadRequestError as e:
            raise AnalyzeError(f'请求被拒绝（400）：{e.message[:200]}') from e
        except a.APIStatusError as e:
            raise AnalyzeError(f'Claude API 错误 {e.status_code}：{e.message[:200]}') from e
        except a.APIConnectionError as e:
            raise AnalyzeError('连不上 Claude API。请检查网络/代理（设置里可以填代理地址）') from e
        u = resp.usage
        self.usage['input'] += (u.input_tokens or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0)
        self.usage['output'] += u.output_tokens or 0
        self.usage['calls'] += 1
        if resp.stop_reason == 'refusal':
            raise AnalyzeError('模型拒绝分析这条内容')
        if resp.stop_reason == 'max_tokens':
            raise AnalyzeError('输出过长被截断')
        if resp.parsed_output is None:
            raise AnalyzeError('模型没有返回可解析的结果')
        return resp.parsed_output

    @staticmethod
    def img(path):
        """图片先记成本地路径；API 引擎发送前转成 base64，Claude Code 引擎让模型自己用 Read 工具读取。"""
        return {'type': 'image_path', 'path': path}

    @staticmethod
    def _b64(path):
        ext = os.path.splitext(path)[1].lower()
        media = {'.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif'}.get(ext, 'image/jpeg')
        with open(path, 'rb') as f:
            return {'type': 'image', 'source': {'type': 'base64', 'media_type': media, 'data': base64.standard_b64encode(f.read()).decode()}}

    # ---- 文案（全部广告，纯文本） ----
    def copy_batch(self, keyword, ads, batch=20):
        out = {}
        for i in range(0, len(ads), batch):
            lite = [{'id': a['id'], 'page': a.get('pageName'), 'daysLive': a.get('daysLive'), 'variants': a.get('variants'),
                     'primaryText': (a.get('body') or '')[:1500], 'headline': a.get('title'), 'linkDescription': a.get('linkDescription'),
                     'cta': a.get('cta')} for a in ads[i:i + batch]]
            text = (f'关键词：{keyword}\n以下是 Meta 广告资料库里在投广告的文案（JSON）。请逐条分析卖点角度、钩子类型、文案结构、优惠，'
                    f'按“能不能让目标用户停下来并点击”打 1-10 分，并给一句话点评。每一条都要分析，id 原样返回。\n' + json.dumps(lite, ensure_ascii=False))
            out.update({r.id: r.model_dump() for r in self._call([{'type': 'text', 'text': text}], CopyBatch).reviews})
        return out

    # ---- 图片广告 ----
    def image_ads(self, keyword, ads, root, batch=4):
        out = {}
        for i in range(0, len(ads), batch):
            content = []
            for a in ads[i:i + batch]:
                m = _metrics(a)
                m.update(primaryText=(a.get('body') or '')[:1200], headline=a.get('title'), linkDescription=a.get('linkDescription'),
                         imageColors=(a.get('imageInfo') or {}).get('colors'), imageAspect=(a.get('imageInfo') or {}).get('aspect'))
                if a.get('cards'):
                    m['cards'] = [{k: c.get(k) for k in ('title', 'body')} for c in a['cards'][:6]]
                content.append({'type': 'text', 'text': json.dumps(m, ensure_ascii=False)})
                for p in (a.get('localImages') or [a.get('thumb')])[:3]:
                    if p:
                        content.append(self.img(os.path.join(root, p)))
            content.append({'type': 'text', 'text': f'关键词：{keyword}。以上是竞对在 Meta 上的图片/轮播广告（每条 JSON 后面是它的图片）。'
                                                    '请逐条识别图中文字、描述画面，并分析产品、卖点、钩子、优点、可改良之处、可借鉴做法，给出改写后的主文案。每一条都要分析，id 原样返回。'})
            out.update({r.id: r.model_dump() for r in self._call(content, CreativeBatch).reviews})
        return out

    # ---- 视频广告 ----
    def video_ad(self, keyword, a, root):
        v = a.get('video') or {}
        tr = v.get('transcript') or {}
        m = _metrics(a)
        m.update(primaryText=(a.get('body') or '')[:1500], headline=a.get('title'), seconds=v.get('seconds'), aspect=v.get('aspect'),
                 sceneCuts=v.get('cuts'), shots=v.get('shots'), avgShotSeconds=v.get('avgShot'),
                 transcript=[f'[{s["t"]}s] {s["text"]}' for s in tr.get('segments', [])][:80] or (tr.get('text') or '（无人声或未转写）'))
        content = []
        for k in ('hookFrames', 'storyboard'):
            if v.get(k):
                content.append(self.img(os.path.join(root, v[k])))
        if not content and a.get('thumb'):
            content.append(self.img(os.path.join(root, a['thumb'])))
        content.append({'type': 'text', 'text': f'关键词：{keyword}。这是竞对在 Meta 上的视频广告。第 1 张图是前 3 秒的钩子帧（每 0.5 秒一帧），'
                                                '第 2 张是逐秒分镜（左上角是时间，含切镜点），transcript 是带时间戳的语音转写（可能只是背景音乐歌词）。'
                                                '请拆解逐镜头脚本，评价钩子、结构和节奏，指出优点、可改良之处和可借鉴的做法，给出改良脚本思路。\n'
                                                + json.dumps(m, ensure_ascii=False)})
        return self._call(content, VideoReview).model_dump()

    # ---- 关键词总结 ----
    def summary(self, job):
        res = job['results']
        ads = res.get('ads', [])

        def lite(a):
            an, cr = a.get('analysis') or {}, a.get('copyReview') or {}
            d = {k: a.get(k) for k in ('id', 'pageName', 'format', 'daysLive', 'variants', 'impRank', 'score', 'verdict', 'domain')}
            d['text'] = (a.get('body') or '')[:240]
            d['headline'] = a.get('title')
            if a.get('product'):
                d['price'] = a['product'].get('price')
                d['compareAt'] = a['product'].get('compareAt')
            if (a.get('video') or {}).get('seconds'):
                d['seconds'] = a['video']['seconds']
                d['avgShot'] = a['video'].get('avgShot')
            if cr:
                d['copy'] = {k: cr.get(k) for k in ('angle', 'hookType', 'formula', 'offer', 'score')}
            if an:
                d['creative'] = {k: an.get(k) for k in ('creativeType', 'hook', 'angle', 'structure')}
                d['creative']['strengths'] = (an.get('strengths') or [])[:2]
            return d
        ins = res.get('insights') or {}
        payload = {
            'keywords': job['keywords'], 'country': job['options'].get('country'),
            'libraryTotals': res.get('totals'), 'collected': len(ads),
            'stats': {k: ins.get(k) for k in ('formats', 'verdicts', 'tags', 'hookTypes', 'daysLive', 'phrases', 'video', 'image', 'ctas')},
            'advertisers': [{k: r.get(k) for k in ('pageName', 'ads', 'maxDays', 'variants', 'bestScore', 'domains', 'newLast14')} for r in ins.get('advertisers', [])[:25]],
            'products': [{k: r.get(k) for k in ('title', 'domain', 'price', 'compareAt', 'ads', 'pages', 'maxDays')} for r in ins.get('products', [])[:25]],
            'sameProduct': ins.get('sameProduct', [])[:10],
            'ads': [lite(a) for a in ads[:80]],
        }
        if job['options'].get('mode') == 'brand':
            pg = (res.get('brand') or {}).get('page') or {}
            payload['brandPage'] = {k: pg.get(k) for k in ('pageName', 'likes', 'pageTotal')}
            text = (f'下面是品牌“{job["keyword"]}”的官方 Facebook 主页（{pg.get("pageName")}）在 Meta 广告资料库里的在投广告样本、本地统计和逐条点评'
                    '（JSON，ads 已按爆款指数从高到低排序）。这是在研究一个对标品牌的投放打法：overview 写它的整体投放策略（素材规模、形式配比、'
                    '品类/产品线分布、常青素材 vs 测试素材），products 写它主推的产品线和价格/优惠，opportunities 写我方作为跨境卖家可以从哪些角度切入或差异化。'
                    '请总结，并给出 3 个可以直接拍/做的素材方案。\n' + json.dumps(payload, ensure_ascii=False))
        else:
            text = ('下面是一个关键词在 Meta 广告资料库里抓到的在投广告、本地统计和逐条点评（JSON，ads 已按爆款指数从高到低排序）。'
                    '请从跨境电商卖家的角度做总结，并给出 3 个可以直接拍/做的素材方案。\n' + json.dumps(payload, ensure_ascii=False))
        return self._call([{'type': 'text', 'text': text}], MarketSummary, max_tokens=24000).model_dump()


# ---------------------------------------------------------------------------
# Claude Code 引擎：调用本机已登录的 Claude Code 命令行（claude -p），用你自己的 Claude 订阅，不需要 API key。
# ---------------------------------------------------------------------------
def find_claude_cli():
    import shutil
    p = shutil.which('claude')
    if p:
        return p
    home = os.path.expanduser('~')
    for c in (os.path.join(home, '.local', 'bin', 'claude.exe'), os.path.join(home, '.local', 'bin', 'claude'),
              os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude.cmd'), '/usr/local/bin/claude', '/opt/homebrew/bin/claude'):
        if c and os.path.exists(c):
            return c
    return None


def schema_for(model_cls):
    """Pydantic 模型 → 内联了 $ref 的 JSON Schema（放进命令行参数更稳）。"""
    sch = model_cls.model_json_schema()
    defs = sch.pop('$defs', {})

    def inline(o):
        if isinstance(o, dict):
            if '$ref' in o:
                return inline(dict(defs[o['$ref'].split('/')[-1]]))
            out = {k: inline(v) for k, v in o.items() if not (k == 'title' and isinstance(v, str))}
            if out.get('type') == 'object':
                out['additionalProperties'] = False
                out.setdefault('required', list(out.get('properties', {}).keys()))
            return out
        if isinstance(o, list):
            return [inline(x) for x in o]
        return o
    return inline(sch)


def cli_env(settings=None):
    """给 claude 子进程用的环境变量：带上代理；去掉“我是某个 Claude Code 会话的子进程”这类变量，否则会报“未登录”。"""
    # 也去掉 API key：环境里有 ANTHROPIC_API_KEY 时 claude 会改用按量付费的 API，这里保证只用订阅登录
    env = {k: v for k, v in os.environ.items()
           if not (k == 'CLAUDECODE' or k.startswith(('CLAUDE_CODE_', 'CLAUDE_AGENT_SDK_')) or k in ('CLAUDE_PID', 'CLAUDE_EFFORT')
                   or k in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'))}
    proxy = (settings or {}).get('proxy') or system_proxy()
    if proxy and not (env.get('HTTPS_PROXY') or env.get('https_proxy')):
        env['HTTPS_PROXY'] = proxy
        env['HTTP_PROXY'] = proxy
    return env


def claude_cli_status(exe=None, timeout=60, settings=None):
    exe = exe or find_claude_cli()
    if not exe:
        return False, '没有安装 Claude Code（claude 命令）'
    try:
        p = subprocess.run([exe, '-p', '--output-format', 'json', '--model', 'haiku', '--max-turns', '1'], input='只回复 OK',
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=cli_env(settings))
        d = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except Exception as e:
        return False, f'无法运行 Claude Code：{str(e)[:100]}'
    if d.get('is_error') or not d:
        msg = str(d.get('result') or p.stderr.strip()[:200])
        if 'login' in msg.lower():
            return False, '已安装，但还没有登录：打开终端运行 claude，输入 /login 登录（国内网络需先给终端设置代理）'
        return False, f'已安装，但调用失败：{msg[:120]}'
    return True, '已安装并已登录'


class ClaudeCodeAnalyzer(Analyzer):
    def __init__(self, settings, workdir):
        self.settings = settings
        self.exe = find_claude_cli()
        if not self.exe:
            raise AnalyzeError('没有找到 Claude Code 命令行（claude）。请先安装 Claude Code（https://claude.com/claude-code），然后在终端运行 claude 并登录')
        self.workdir = workdir
        self.model = settings.get('cc_model') or 'sonnet'
        self.usage = {'input': 0, 'output': 0, 'calls': 0, 'engine': 'Claude Code'}

    def _call(self, content, schema, max_tokens=None):
        try:
            return self._call_once(content, schema)
        except AnalyzeError as e:
            if '格式' not in str(e):
                raise
            return self._call_once(content + [{'type': 'text', 'text': '注意：上一次的回答没有按要求输出。这次务必只给出符合 JSON Schema 的结果。'}], schema)

    def _call_once(self, content, schema):
        lines, n = [SYSTEM, ''], 0
        for c in content:
            if c.get('type') == 'image_path':
                n += 1
                rel = os.path.relpath(c['path'], self.workdir).replace(os.sep, '/')
                lines.append(f'[图片 {n}：请用 Read 工具查看文件 {rel}]')
            else:
                lines.append(c['text'])
        if n:
            lines.append('\n要求：先用 Read 工具逐一查看上面列出的全部图片文件，再作答。只读取列出的文件，不要修改任何文件。')
        lines.append('最终结果必须符合给定的 JSON Schema。')
        cmd = [self.exe, '-p', '--output-format', 'json', '--json-schema', json.dumps(schema_for(schema), ensure_ascii=False),
               '--allowedTools', 'Read', '--model', self.model]
        try:
            p = subprocess.run(cmd, input='\n'.join(lines), capture_output=True, text=True, encoding='utf-8', errors='replace',
                               cwd=self.workdir, timeout=900, env=cli_env(self.settings))
        except subprocess.TimeoutExpired as e:
            raise AnalyzeError('Claude Code 超过 15 分钟没有返回') from e
        except OSError as e:
            raise AnalyzeError(f'无法运行 Claude Code：{e}') from e
        try:
            d = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
        except ValueError:
            d = {}
        res_text = str(d.get('result') or '')
        if not d or d.get('is_error'):
            msg = res_text or p.stderr.strip()[:300] or f'退出码 {p.returncode}'
            low = msg.lower()
            if 'not logged in' in low or '/login' in low:
                raise AnalyzeError('Claude Code 还没有登录。请打开终端运行 claude，输入 /login 登录后，再点“AI 分析”')
            if 'limit' in low or 'usage' in low or 'quota' in low:
                raise AnalyzeError(f'Claude 订阅的使用额度达到上限：{msg[:200]}')
            raise AnalyzeError(f'Claude Code 返回错误：{msg[:300]}')
        u = d.get('usage') or {}
        self.usage['input'] += (u.get('input_tokens') or 0) + (u.get('cache_read_input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0)
        self.usage['output'] += u.get('output_tokens') or 0
        self.usage['calls'] += 1
        data = d.get('structured_output')
        if data is None:
            m = re.search(r'\{.*\}', res_text, re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except ValueError:
                    data = None
        try:
            if data is None:
                raise ValueError('没有结构化结果')
            return schema.model_validate(data)
        except Exception as e:
            try:
                with open(os.path.join(self.workdir, 'debug_claude_code.txt'), 'w', encoding='utf-8') as f:
                    f.write(f'{e}\n\n--- stdout ---\n{p.stdout[-20000:]}\n\n--- stderr ---\n{p.stderr[-5000:]}')
            except OSError:
                pass
            raise AnalyzeError(f'Claude Code 返回的结果格式不符（{str(e)[:120]}），原始输出已保存到任务文件夹 debug_claude_code.txt') from e
