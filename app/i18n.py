"""后端文字的中英文切换。

用法：T('合并去重后 {n} 条广告', n=12)。中文原文就是键；英文模式下查 EN 表，查不到就原样返回中文。
语言按线程区分：任务线程在开始执行某个任务时 set_lang(任务的语言)，网页请求线程按面板当前设置的语言。
"""
import threading

_local = threading.local()


def set_lang(lang):
    _local.lang = 'en' if lang == 'en' else 'zh'


def get_lang():
    lang = getattr(_local, 'lang', None)
    if lang:
        return lang
    from . import config
    return 'en' if config.load_settings().get('lang') == 'en' else 'zh'


def T(zh, _lang=None, **kw):
    lang = _lang or get_lang()
    s = EN.get(zh, zh) if lang == 'en' else zh
    return s.format(**kw) if kw else s


EN = {
    # ---- 通用 ----
    '；': '; ',
    '、': ', ',
    # ---- 任务步骤 ----
    '启动浏览器': 'Launch browser',
    '采集广告资料库': 'Collect from Ad Library',
    '落地页商品与价格': 'Landing products & prices',
    '下载素材 · 分镜 · 转写': 'Media · storyboard · transcript',
    '本地分析': 'Local analysis',
    'AI 分析': 'AI analysis',
    # ---- 任务流程 jobs.py ----
    '任务': 'Job',
    '面板被关闭，任务中断。可以点“重新抓取”。': 'The panel was closed and the job was interrupted. Click "Re-run" to start it again.',
    '素材不存在': 'Creative not found',
    '任务正在运行，等它结束后再拆解单条素材': 'The job is still running. Wait for it to finish before analyzing a single creative.',
    '这条素材已经在排队了': 'This creative is already queued.',
    '排队中': 'Queued',
    '任务已取消': 'Job cancelled',
    '任务出错：{e}': 'Job failed: {e}',
    '内置 Chromium': 'built-in Chromium',
    '无法启动浏览器。请先运行“1-安装”，或安装 Google Chrome。详情：{d}': 'Could not start a browser. Run the installer first, or install Google Chrome. Details: {d}',
    '正在启动浏览器': 'Starting the browser',
    '浏览器没有启动': 'Browser did not start',
    '已启动 {name}': 'Started {name}',
    '正在打开 Meta 广告资料库': 'Opening the Meta Ad Library',
    '广告资料库': 'Ad Library',
    '没有采集到广告': 'No ads collected',
    '“{k}” 在投 {v} 条': '"{k}": {v} active',
    '合并去重后 {n} 条广告': '{n} unique ads after merging',
    '（资料库：{tot}）': ' (Ad Library: {tot})',
    '这个关键词在所选国家没有在投广告。换一个更宽泛的英文词，或者把国家改成“全部国家”再试。':
        'No active ads for this keyword in the selected country. Try a broader English term, or set the country to "All countries".',
    '连续几次查询没有返回广告，可能被 Meta 暂时限流，已提前结束采集。过一会儿再试，或换一个代理节点。':
        'Several queries in a row returned no ads, so Meta may be rate-limiting. Collection stopped early. Try again later or switch to another proxy node.',
    '这个主页在投 {pt} 条，本次拿到 {n} 条（{pct}）。未登录时 Meta 每次只返回 30 条、翻页被限流，工具用多组排序/形式/平台组合和“主页内搜索”滚雪球来多拿素材。想要更多：选“深度”，或在“主页内关键词”里填品类词（如 dog food, cat litter）。':
        'This page has {pt} active ads; this run collected {n} ({pct}). Without a Facebook login, Meta returns only 30 ads per page load and blocks paging, '
        'so the tool combines several sort / format / platform views and snowballs through in-page searches. For more, choose "Deep", '
        'or enter category terms under "In-page keywords" (e.g. dog food, cat litter).',
    '未登录时 Meta 每次只返回 30 条（翻页接口会被限流），所以工具用多组排序/筛选组合来多拿素材。想要更多，可以在“采集深度”里选“深度”，或者再加几个相关关键词（用逗号分隔）。':
        'Without a Facebook login, Meta returns only 30 ads per page load (paging is rate-limited), so the tool combines several sort / filter views. '
        'For more, choose "Deep" depth or add a few related keywords (comma-separated).',
    '正在读取落地页商品信息': 'Reading landing product pages',
    '{n} 条广告落地到商品页，读到 {p} 个 Shopify 商品的售价/原价': '{n} ads link to product pages; read prices for {p} Shopify products',
    '读取失败：{e}': 'Failed to read: {e}',
    '设置里关闭了': 'Turned off in Settings',
    '素材': 'Media',
    '没有找到 ffmpeg（imageio-ffmpeg），视频无法分镜。请重新运行“1-安装”。': 'ffmpeg (imageio-ffmpeg) was not found, so videos cannot be storyboarded. Run the installer again.',
    '语音转写': 'Transcription',
    '没有安装 faster-whisper，视频不做语音转写。需要的话运行“1-安装”时选择安装语音转写。': 'faster-whisper is not installed, so videos are not transcribed. Run the installer again to add it.',
    '正在下载素材': 'Downloading media',
    '视频 {v} 条（分镜、切镜节奏、语音转写），图片广告 {i} 条，缩略图 {t} 张': '{v} videos (storyboard, cut pace, transcript), {i} image ads, {t} thumbnails',
    '视频 {v} 条（分镜、切镜节奏），图片广告 {i} 条，缩略图 {t} 张': '{v} videos (storyboard, cut pace), {i} image ads, {t} thumbnails',
    '；{f} 条失败': '; {f} failed',
    '正在统计': 'Computing stats',
    '{a} 个店铺主页 · {p} 个落地商品 · {s} 组同款竞争 · {e} 条常青爆款': '{a} advertiser pages · {p} landing products · {s} same-product groups · {e} evergreen winners',
    '手动选择的主页': 'Page chosen manually',
    '资料库里没有找到“{t}”相关的广告主页': 'No advertiser page matching "{t}" in the Ad Library',
    '品牌主页': 'Brand page',
    '按“{t}”搜索没有找到任何广告主页。试试品牌的英文名、官网域名（如 chewy.com）或 Facebook 主页链接。':
        'Searching "{t}" found no advertiser pages. Try the brand\'s English name, its website domain (e.g. chewy.com) or its Facebook page URL.',
    '没有识别到主页': 'No page identified',
    '自动选择了“{n}”，但把握不大。请在“品牌主页”里核对，不对的话点候选主页旁的“改抓这个主页”。':
        'Picked "{n}" automatically, but with low confidence. Check the "Brand page" tab, and click "Use this page" next to the right candidate if needed.',
    '没有素材可分析': 'No creatives to analyze',
    '本次任务没有勾选“抓完自动 AI 分析”，可以稍后点“AI 分析”': 'Auto AI analysis was off for this job. Click "AI analysis" to run it.',
    '设置里选择了“不做 AI 分析”': 'AI analysis is turned off in Settings',
    '未配置 Claude API key，跳过 AI 分析': 'No Claude API key configured; AI analysis skipped',
    '分析引擎选的是 Claude API，但没有填 API key。可以在“设置”里填 key，或者改成 Claude Code（用订阅，不需要 key），然后点“AI 分析”。':
        'The AI engine is set to Claude API, but no API key was entered. Add a key in Settings, or switch to Claude Code (uses your subscription, no key needed), then click "AI analysis".',
    '分析引擎：{e}（{m}）': 'AI engine: {e} ({m})',
    '正在分析：{l}': 'Analyzing: {l}',
    '{l}：{e}': '{l}: {e}',
    '分析失败 {l}：{e}': 'Analysis failed for {l}: {e}',
    '文案 {a}–{b} / {n} 段': 'copy {a}–{b} of {n}',
    '图片素材（{n} 条）': 'image creatives ({n})',
    '视频 #{r} {p}': 'video #{r} {p}',
    '关键词总结': 'summary',
    '完成 {c} 次调用（输入约 {i} tokens，输出约 {o} tokens）': 'Done: {c} calls (about {i} input tokens, {o} output tokens)',
    '；{n} 项失败': '; {n} failed',
    '设置里的分析引擎是“不做 AI 分析”': 'AI analysis is turned off in Settings',
    '分析引擎是 Claude API，但没有填 API key': 'The AI engine is Claude API, but no API key is set',
    '正在下载视频、生成分镜、语音转写': 'Downloading the video, building the storyboard and transcript',
    '正在下载视频、生成分镜': 'Downloading the video and building the storyboard',
    '正在用 AI 拆解（通常 1–3 分钟）': 'Analyzing with AI (usually 1–3 minutes)',
    '已拆解（{n} 次调用）': 'Analyzed ({n} calls)',
    '模型没有返回这条素材的结果': 'The model returned no result for this creative',
    '拆解失败：{e}': 'Analysis failed: {e}',
    # ---- 资料库采集 meta.py ----
    '曝光最高 · 全部': 'Top impressions · all',
    '曝光最高 · 视频': 'Top impressions · video',
    '曝光最高 · 图片': 'Top impressions · image',
    '最新上线 · 全部': 'Newest · all',
    '最新上线 · 视频': 'Newest · video',
    '最新上线 · 图片': 'Newest · image',
    '曝光最高 · Instagram': 'Top impressions · Instagram',
    '曝光最高 · Facebook': 'Top impressions · Facebook',
    '最新上线 · Instagram': 'Newest · Instagram',
    '曝光最高 · 精确词组': 'Top impressions · exact phrase',
    'Facebook 跳转到了登录/验证页面。换一个代理节点，或者过一会儿再试': 'Facebook redirected to a login / checkpoint page. Switch to another proxy node, or try again later.',
    'Meta 要求验证码。在设置里勾选“显示浏览器窗口”后重试，手动完成验证；或者换一个代理节点': 'Meta asked for a CAPTCHA. Turn on "Show browser window" in Settings and retry to solve it by hand, or switch to another proxy node.',
    '“{kw}” · {label}（{i}/{n}）': '"{kw}" · {label} ({i}/{n})',
    '查询失败 {kw} · {label}：{e}': 'Query failed {kw} · {label}: {e}',
    '{kw} · {label}：资料库共 {t} 条，本次拿到 {g} 条，新增 {n} 条': '{kw} · {label}: {t} in the library, got {g}, {n} new',
    '连续 3 次查询没有返回广告，可能被 Meta 限流，提前结束采集': '3 queries in a row returned no ads; Meta may be rate-limiting. Stopping early.',
    # ---- 品牌模式 brand.py ----
    '主页 · 曝光最高': 'Page · top impressions',
    '主页 · 最新上线': 'Page · newest',
    '主页 · 视频 · 曝光最高': 'Page · video · top impressions',
    '主页 · 图片 · 曝光最高': 'Page · image · top impressions',
    '主页 · 视频 · 最新': 'Page · video · newest',
    '主页 · 图片 · 最新': 'Page · image · newest',
    '主页 · 图文 · 曝光最高': 'Page · meme · top impressions',
    '主页 · Audience Network': 'Page · Audience Network',
    '主页 · Messenger': 'Page · Messenger',
    '主页 · 图文 · 最新': 'Page · meme · newest',
    '主页内搜索 · {term}': 'In-page search · {term}',
    '直接指定的主页 ID': 'Page ID given directly',
    '正在识别“{t}”的官方主页（搜索 {s}）': 'Finding the official page for "{t}" (searching {s})',
    '识别主页时查询失败（{s}）：{e}': 'Query failed while finding the page ({s}): {e}',
    '主页名称与品牌一致': 'page name matches the brand',
    '主页名称包含品牌名': 'page name contains the brand',
    '主页链接一致': 'page URL matches',
    '主页链接名与品牌一致': 'page URL name matches the brand',
    '{n} 条广告落地到品牌域名': '{n} ads link to the brand domain',
    '{n} 粉丝': '{n} followers',
    '识别主页：{n}（{id}），得分 {s}：{r}': 'Identified page: {n} ({id}), score {s}: {r}',
    '查询失败 {label}：{e}': 'Query failed {label}: {e}',
    '{label}：共 {t} 条，拿到 {g} 条，新增 {n} 条（累计 {c}）': '{label}: {t} total, got {g}, {n} new ({c} so far)',
    '连续 3 次查询没有返回广告，可能被 Meta 暂时限流。过一会儿再试，或换一个代理节点': '3 queries in a row returned no ads; Meta may be rate-limiting. Try again later or switch to another proxy node.',
    '{label}（{i}/{n}）· 已拿到 {c} 条': '{label} ({i}/{n}) · {c} so far',
    '主页内搜索“{t}”（{d}/{l}）· 已拿到 {n} 条': 'In-page search "{t}" ({d}/{l}) · {n} so far',
    '连续 4 个搜索词几乎没有新广告，停止主页内搜索': '4 search terms in a row added almost nothing new; stopping the in-page search',
    # ---- 落地页 shop.py ----
    '读取商品页 {i}/{n}：{h}': 'Reading product page {i}/{n}: {h}',
    '落地页：{r} 个商品页，读到 {p} 个 Shopify 商品的价格（{s} 家店）': 'Landing pages: {r} product pages, prices for {p} Shopify products ({s} stores)',
    # ---- 素材 media.py ----
    '转写失败：{e}': 'Transcription failed: {e}',
    '下载图片和封面 {i}/{n}': 'Downloading images and posters {i}/{n}',
    '图片下载失败 {id}：{e}': 'Image download failed {id}: {e}',
    '处理视频 {i}/{n}（{p}）：下载、分镜、语音转写': 'Processing video {i}/{n} ({p}): download, storyboard, transcript',
    '处理视频 {i}/{n}（{p}）：下载、分镜': 'Processing video {i}/{n} ({p}): download, storyboard',
    '视频处理失败 {id}：{e}': 'Video processing failed {id}: {e}',
    # ---- 面板服务 main.py ----
    'ffmpeg（视频分镜）': 'ffmpeg (video storyboards)',
    '访问 Facebook': 'Facebook access',
    'AI 分析：Claude Code': 'AI: Claude Code',
    'AI 分析：Claude API': 'AI: Claude API',
    '已安装': 'Installed',
    '未安装，请先运行“1-安装”': 'Not installed. Run the installer first.',
    '未安装，请重新运行“1-安装”': 'Not installed. Run the installer again.',
    '已安装 faster-whisper（模型 {m}）': 'faster-whisper installed (model {m})',
    '未安装 faster-whisper（不影响抓取，只是视频没有口播文字）': 'faster-whisper not installed (scraping still works; videos just have no transcript)',
    '正常': 'OK',
    '正常（代理 {p}）': 'OK (proxy {p})',
    '失败：{e}。请开启代理/VPN，或在设置里填写代理地址': 'Failed: {e}. Turn on a proxy / VPN, or enter a proxy address in Settings.',
    '（不影响抓取和本地分析）': ' (scraping and local analysis still work)',
    '已填写 API key': 'API key entered',
    '未填写 API key（不影响抓取和本地分析）': 'No API key (scraping and local analysis still work)',
    '已关闭（只抓取 + 本地分析）': 'Off (scraping + local analysis only)',
    '已安装并已登录': 'Installed and logged in',
    '没有安装 Claude Code（claude 命令）': 'Claude Code (the claude command) is not installed',
    '已安装，但还没有登录：打开终端运行 claude，输入 /login 登录（国内网络需先给终端设置代理）': 'Installed but not logged in: run claude in a terminal and type /login (in mainland China, set a proxy for the terminal first)',
    '无法运行 Claude Code：{e}': 'Could not run Claude Code: {e}',
    '已安装，但调用失败：{e}': 'Installed, but the test call failed: {e}',
    '任务不存在': 'Job not found',
    '请输入关键词': 'Please enter a keyword',
    '任务正在运行，稍后再试': 'The job is running; try again later',
    '报告.html': 'report.html',
    '素材清单.csv': 'creatives.csv',
    '面板已经在运行（端口 {p} 被占用），直接打开：{u}': 'The panel is already running (port {p} in use). Opening {u}',
    '面板已启动：{u}  （关闭这个窗口即可停止）': 'Panel started: {u}  (close this window to stop it)',
    # CSV 列名
    '排名': 'Rank', '爆款指数': 'Winner score', '判定': 'Verdict', '资料库编号': 'Library ID', '资料库链接': 'Library URL',
    '主页': 'Page', '主页粉丝': 'Page followers', '形式': 'Format', '上线日期': 'Start date', '在投天数': 'Days running',
    '同素材广告数': 'Ads using this creative', '曝光排序位置': 'Impression rank', '平台': 'Platforms', '主文案': 'Primary text',
    '标题': 'Headline', '链接描述': 'Link description', '落地页': 'Landing page', '域名': 'Domain', '商品名': 'Product',
    '售价': 'Price', '原价': 'Compare-at price', '文案标签': 'Copy tags', '开头类型': 'Opening type', '视频秒数': 'Video seconds',
    '镜头数': 'Shots', '平均镜头时长': 'Avg shot length', '口播转写': 'Transcript', 'AI 卖点角度': 'AI angle',
    'AI 钩子类型': 'AI hook type', 'AI 文案结构': 'AI copy structure', 'AI 文案分': 'AI copy score', 'AI 文案点评': 'AI copy note',
    'AI 素材形式': 'AI creative type', 'AI 钩子': 'AI hook', 'AI 优点': 'AI strengths', 'AI 可改良': 'AI improvements',
    'AI 可借鉴': 'AI takeaways', 'AI 改写': 'AI rewrite', '收藏': 'Starred',
    # 分类值（本地分析写进数据里的中文值；CSV 导出时翻译，面板前端另有同样的表）
    '常青爆款': 'Evergreen winner', '新起量': 'Rising', '稳定在投': 'Steady', '在投': 'Active', '测试中': 'Testing',
    '折扣': 'Discount', '买赠/赠品': 'BOGO / gift', '包邮': 'Free shipping', '限时/稀缺': 'Urgency / scarcity',
    '社会证明': 'Social proof', '无风险保障': 'Risk-free guarantee', '痛点': 'Pain point', '专业背书': 'Authority',
    '前后对比': 'Before / after', '节日/送礼': 'Holiday / gifting', '价格锚点': 'Price anchor',
    '提问': 'Question', '数字开头': 'Starts with a number', '表情开头': 'Starts with an emoji', '痛点开头': 'Pain-point opener',
    '全大写': 'ALL CAPS', '感叹句': 'Exclamation', '陈述句': 'Statement',
    # ---- 设置 config.py ----
    'Claude Opus 5.5（分析最细，较贵）': 'Claude Opus 5.5 (most detailed, pricier)',
    'Claude Sonnet 5.5（推荐，性价比高）': 'Claude Sonnet 5.5 (recommended, best value)',
    'Claude Haiku 5.5（最便宜，分析较浅）': 'Claude Haiku 5.5 (cheapest, lighter analysis)',
    'Claude Code（用你的 Claude 订阅，不需要 API key）': 'Claude Code (uses your Claude subscription, no API key)',
    'Claude API（需要 API key，按量付费）': 'Claude API (needs an API key, pay as you go)',
    '不做 AI 分析（只抓取 + 本地分析）': 'No AI analysis (scraping + local analysis only)',
    'Sonnet（推荐）': 'Sonnet (recommended)',
    'Opus（分析更细，更耗额度）': 'Opus (more detailed, uses more quota)',
    'Haiku（最快、最省额度）': 'Haiku (fastest, least quota)',
    'tiny（最快）': 'tiny (fastest)',
    'small（推荐）': 'small (recommended)',
    'medium（最准，较慢）': 'medium (most accurate, slower)',
    # ---- AI 分析 analyze.py ----
    'API key 无效，请在“设置”里检查': 'The API key is invalid. Check it in Settings.',
    'API key 没有权限：{e}': 'The API key lacks permission: {e}',
    '模型不存在或不可用：{m}': 'Model not found or unavailable: {m}',
    'API 调用太频繁或额度不足（429），请稍后再试': 'Too many API calls or not enough credit (429). Try again later.',
    '请求被拒绝（400）：{e}': 'Request rejected (400): {e}',
    'Claude API 错误 {c}：{e}': 'Claude API error {c}: {e}',
    '连不上 Claude API。请检查网络/代理（设置里可以填代理地址）': 'Cannot reach the Claude API. Check your network / proxy (you can set a proxy in Settings).',
    '模型拒绝分析这条内容': 'The model declined to analyze this content',
    '输出过长被截断': 'The output was too long and got cut off',
    '模型没有返回可解析的结果': 'The model did not return a parsable result',
    '没有找到 Claude Code 命令行（claude）。请先安装 Claude Code（https://claude.com/claude-code），然后在终端运行 claude 并登录':
        'Claude Code (the claude command) was not found. Install Claude Code (https://claude.com/claude-code), then run claude in a terminal and log in.',
    'Claude Code 超过 15 分钟没有返回': 'Claude Code did not respond within 15 minutes',
    'Claude Code 还没有登录。请打开终端运行 claude，输入 /login 登录后，再点“AI 分析”': 'Claude Code is not logged in. Open a terminal, run claude, type /login, then click "AI analysis" again.',
    'Claude 订阅的使用额度达到上限：{e}': 'Your Claude subscription usage limit was reached: {e}',
    'Claude Code 返回错误：{e}': 'Claude Code returned an error: {e}',
    'Claude Code 返回的结果格式不符（{e}），原始输出已保存到任务文件夹 debug_claude_code.txt': 'Claude Code returned an unexpected format ({e}); the raw output was saved to debug_claude_code.txt in the job folder',
}
