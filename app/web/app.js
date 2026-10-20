/* Meta 素材侦察面板：前端逻辑。导出的静态报告也用这份代码（window.STATIC_JOB 存在时为静态模式）。 */
const STATIC = window.STATIC_JOB || null;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmt = n => n == null ? '—' : Number(n).toLocaleString();
const state = {settings: null, jobs: [], cur: null, job: null, tab: 'summary', timer: null, sig: '', f: {q: '', format: '', verdict: '', sort: 'score', page: '', star: false}, limit: 60, drawer: null, starred: null, view: 'welcome'};
const STEP_ICON = {pending: '○', running: '◐', done: '✓', failed: '✕', skipped: '–'};
// 步骤标题按 key 显示（旧任务里存的是创建时的语言）
const STEP_LABEL = {browser: '启动浏览器', collect: '采集广告资料库', shop: '落地页商品与价格', media: '下载素材 · 分镜 · 转写', local: '本地分析', analysis: 'AI 分析'};

/* ---------------- 中英文切换 ---------------- */
// 界面文字：中文原文就是键，英文模式下查 EN 表；{n} 这类占位符用 t(文本, {n: 1}) 填入
let LANG = 'zh';
const EN = {
  // 顶栏 / 侧栏
  'Meta 素材侦察面板': 'Meta Ad Spy Panel', '· 跨境电商': '· for e-commerce', '★ 收藏夹': '★ Favorites', '环境检查': 'Check setup', '设置': 'Settings',
  '关键词模式': 'Keyword mode', '品牌模式': 'Brand mode', '投放国家': 'Country', '采集深度': 'Depth', '只看在投广告': 'Active ads only',
  '抓完自动 AI 分析（引擎在“设置”里选）': 'Run AI analysis when done (engine in Settings)', '素材数量': 'How many creatives',
  '拆解视频': 'Videos', '下载图片': 'Images', 'AI 深拆': 'AI deep-dives',
  '按“爆款指数”从高到低处理。文案的 AI 点评覆盖全部广告；“AI 深拆”是看图/看分镜的逐条拆解。其他素材可以在详情里单独点“AI 拆解”。':
    'Processed from the highest winner score down. AI copy reviews cover every ad; "AI deep-dives" look at the images / storyboards one by one. Any other creative can be analyzed from its detail view.',
  '开始抓取': 'Start', '历史任务': 'History', '主页内关键词（可选）': 'In-page keywords (optional)', '例如 dog food, cat litter（留空自动挑词）': 'e.g. dog food, cat litter (leave empty to pick automatically)',
  '还没有任务': 'No jobs yet', '{n} 条素材': '{n} creatives',
  '按产品词搜全网在投广告，看这个品类谁在投、怎么投。': 'Search active ads by product keyword to see who advertises in a niche and how.',
  '产品词，例如 posture corrector\n多个词用逗号分隔（最多 5 个）': 'Product keyword, e.g. posture corrector\nSeparate several with commas (max 5)',
  '快速（每个词 2 次查询，约 60 条）': 'Quick (2 queries per keyword, ~60 ads)', '标准（每个词 6 次查询，约 120–180 条）': 'Standard (6 queries per keyword, ~120–180 ads)',
  '深度（每个词 10 次查询，约 200–300 条）': 'Deep (10 queries per keyword, ~200–300 ads)',
  '输入品牌名、官网域名或 Facebook 主页链接，自动识别官方主页，只抓这个主页的广告。': 'Enter a brand name, website domain or Facebook page URL. The panel finds the official page and collects only its ads.',
  '例如 chewy、chewy.com\n或 https://www.facebook.com/chewy': 'e.g. chewy, chewy.com\nor https://www.facebook.com/chewy',
  '快速（约 6 次查询，100–150 条）': 'Quick (~6 queries, 100–150 ads)', '标准（约 18 次查询，250–400 条）': 'Standard (~18 queries, 250–400 ads)', '深度（约 40 次查询，500–900 条）': 'Deep (~40 queries, 500–900 ads)',
  // 任务状态
  '排队中': 'Queued', '抓取中': 'Running', '完成': 'Done', '失败': 'Failed', '已取消': 'Cancelled',
  // 素材形式
  '视频': 'Video', '图片': 'Image', '轮播': 'Carousel', '动态素材': 'Dynamic', '商品目录': 'Catalog', '多图': 'Multi-image', '多视频': 'Multi-video', '其他': 'Other',
  // 通用
  '暂无数据': 'No data', '暂无': 'None', '{k} 这周：{v} 条': 'Week of {k}: {v}', '没有缩略图': 'No thumbnail', '{n} 张': '{n} images', '爆款指数': 'Winner score',
  '取消收藏': 'Unstar', '收藏': 'Star', '（无文案）': '(no copy)', '在投 {n} 天': '{n} days running', '{n} 条同素材': '{n} ads use it', '曝光第 {n}': 'Impression #{n}',
  '{n} 天': '{n} days', '主页↗': 'Page↗', '打开↗': 'Open↗', '看素材': 'View', '当前': 'Current',
  // 总结
  '采集中，请稍候…': 'Collecting, please wait…', '没有采集到广告（原因见上方提示）': 'No ads collected (see the notes above)',
  '主页在投广告总数': 'Active ads on this page', '资料库在投总数': 'Active ads in the library', '（多个词相加）': ' (keywords added up)', '本次采集（去重后）': 'Collected (unique)',
  '本次覆盖主页在投广告的比例': 'Share of the page\'s active ads collected', '在投的店铺主页': 'Advertiser pages', '常青爆款 / 新起量': 'Evergreen winners / rising',
  '视频素材占比': 'Video share', '在投天数中位数': 'Median days running', '视频时长中位数': 'Median video length', ' · 平均 {n}s 一个镜头': ' · {n}s per shot on average',
  '落地页售价中位数': 'Median landing price', '（{n} 个商品，{a}–{b}；各店默认币种）': ' ({n} products, {a}–{b}; each store\'s own currency)',
  '爆款指数最高的素材': 'Top creatives by winner score',
  '（在投天数 + 同素材广告数 + 曝光排序位置 + 平台数，Meta 不公开花费和点赞，这是用公开字段做的近似）':
    '(days running + ads sharing the creative + impression rank + platforms. Meta does not publish spend or likes, so this is an estimate from public fields)',
  '素材形式': 'Formats', '投放状态判定': 'Verdicts', '在投天数分布': 'Days running', '近半年每周新上线（本次样本）': 'New ads per week, last 6 months (this sample)',
  '文案里的卖点/促销手法': 'Selling points & promos in copy', '文案开头类型': 'Copy openings', '文案长度': 'Copy length', 'CTA 按钮': 'CTA buttons',
  '视频时长（已拆解 {n} 条）': 'Video length ({n} analyzed)', '画幅：{a} · 有口播 {n} 条': 'Aspect: {a} · {n} with voice-over', '图片画幅与色调（{n} 张）': 'Image aspect & tone ({n})',
  '投放平台': 'Platforms', '高频词组': 'Frequent phrases', '（按使用的店铺数）': '(by number of advertisers using it)',
  '还没有 AI 总结。': 'No AI summary yet. ', '竞争格局（AI）': 'Market overview (AI)', '品牌投放策略（AI）': 'Brand strategy (AI)', '产品与价格带': 'Products & price range',
  '关键发现': 'Key findings', '给你的素材建议': 'Creative recommendations', '空白机会': 'Gaps to exploit', '跑得久的卖点角度': 'Long-running angles',
  '优惠与价格策略': 'Offers & pricing', '开头钩子套路': 'Hook patterns', '视频脚本与剪辑套路': 'Video script & editing patterns', '图片画面套路': 'Image patterns',
  '可以直接拍的 3 个素材方案': '3 ready-to-shoot concepts', '角度：': 'Angle: ', '前 3 秒：': 'First 3 seconds: ', '参考：': 'References: ', '本地统计': 'Local stats',
  // 素材库
  '搜索文案、店铺、落地页、口播…': 'Search copy, advertisers, landing pages, voice-over…', '全部形式': 'All formats', '图片类': 'Image-based', '全部判定': 'All verdicts',
  '按爆款指数': 'By winner score', '按在投天数': 'By days running', '按同素材广告数': 'By ads sharing the creative', '按曝光排序位置': 'By impression rank',
  '最新上线在前': 'Newest first', '按 AI 文案分': 'By AI copy score', '只看收藏': 'Starred only', '{a} / {b} 条': '{a} / {b}', '只看店铺：': 'Advertiser: ', '清除': 'Clear',
  '没有符合条件的素材': 'No creatives match', '再显示 {n} 条': 'Show {n} more',
  // 拆解
  '时间': 'Time', '画面': 'Visual', '口播/声音': 'Voice / sound', '作用': 'Purpose', '产品': 'Product', '形式': 'Format', '卖点角度': 'Angle', '钩子': 'Hook',
  '结构': 'Structure', '节奏': 'Pace', '图中文字': 'Text in image', '目标人群': 'Audience', '优点': 'Strengths', '可改良的空间': 'Room to improve',
  '我方可以直接借鉴': 'What you can borrow', '改良脚本思路': 'Improved script', '改写后的主文案': 'Rewritten primary text', '钩子类型': 'Hook type',
  '文案结构': 'Copy structure', '优惠': 'Offer', '文案力': 'Copy score',
  '还没有拆解过的视频（在“素材数量”里调大“拆解视频”，或在素材详情里点“AI 拆解”）': 'No videos analyzed yet (raise "Videos" under "How many creatives", or click "AI analyze" in a creative\'s detail view).',
  '已下载并拆解 {n} 条视频（按爆款指数）': '{n} videos downloaded and analyzed (by winner score)', '；另有 {n} 条视频未下载，可在素材库里打开详情单独拆解': '; {n} more videos not downloaded (open one in the library to analyze it)',
  '{n} 个镜头': '{n} shots', '前 3 秒钩子帧': 'First 3 seconds', '前 3 秒画面': 'First 3 seconds', '口播：': 'Voice-over: ', '无口播（或只有背景音乐）': 'No voice-over (or music only)',
  'AI 拆解：': 'AI breakdown: ', 'AI 拆解这条': 'AI analyze', '没有图片素材': 'No image creatives',
  '{n} 条有文案 · AI 点评 {m} 条': '{n} with copy · {m} reviewed by AI', '店铺': 'Advertiser', '主文案': 'Primary text', '标题 / CTA': 'Headline / CTA',
  '本地标签': 'Tags', 'AI 角度 · 结构': 'AI angle · structure', 'AI 分': 'AI score', '在投': 'Running', '{n} 字符': '{n} chars', '{n} 表情': '{n} emoji',
  // 店铺 / 商品 / 查询
  '点店铺名可以在素材库里只看这家店。“同素材”= 资料库里“N 条广告使用了这个素材和文案”的合计，越多说明在加预算铺量。':
    'Click an advertiser to filter the library. "Shared" adds up the library\'s "N ads use this creative and text" counts; more usually means more budget behind it.',
  '店铺主页': 'Advertiser page', '粉丝': 'Followers', '素材数': 'Ads', '视频/图片': 'Video / image', '最长在投': 'Longest running', '中位在投': 'Median running',
  '同素材合计': 'Shared total', '近 14 天新上': 'New in 14 days', '最高爆款指数': 'Best score', '落地域名': 'Landing domains',
  '同款竞争：同一个商品被多家店推': 'Same product, several stores', '商品': 'Product', '广告数': 'Ads', '售价': 'Price',
  '同一段文案被多个主页使用（铺货 / 同源素材）': 'Same copy used by several pages (dropshipping / shared source)', '同一张图/同一条视频被多个主页使用': 'Same image or video used by several pages',
  '落地商品（{n}）': 'Landing products ({n})', '广告落地到 Shopify 商品页时，读取了公开的商品名、售价、原价和上架日期。价格是店铺默认币种。':
    'For ads that link to a Shopify product page, the public product title, price, compare-at price and launch date were read. Prices are in each store\'s own currency.',
  '原价': 'Compare at', '折扣': 'Discount', '上架': 'Launched', '推广主页': 'Advertisers', '素材': 'Creative', '{n} 个规格': '{n} variants',
  '未登录时 Meta 每次只返回 30 条，所以用多组排序/筛选组合分别查询，再合并去重。点链接可以在浏览器里打开同样的资料库页面。':
    'Without a login, Meta returns only 30 ads per page load, so several sort / filter views are queried and merged. Click a link to open the same Ad Library page in your browser.',
  '关键词': 'Keyword', '查询': 'Query', '资料库总数': 'Library total', '拿到': 'Got', '新增': 'New', '链接': 'Link',
  // 品牌
  '🏷 品牌模式：正在识别“{k}”的官方主页…': '🏷 Brand mode: finding the official page for "{k}"…', '🏷 品牌模式 · 官方主页': '🏷 Brand mode · official page',
  '{n} 粉丝 · ': '{n} followers · ', '主页在投 {a} 条 · 本次拿到 {b} 条': '{a} active ads on the page · {b} collected', ' · 识别依据：': ' · Matched on: ',
  '不是这个主页？': 'Wrong page?', '没有其他候选主页（主页是直接指定的）': 'No other candidates (the page was given directly)',
  '按“{k}”搜索资料库时出现的广告主页，按匹配得分排序。选错了就点“改抓这个主页”，会用同样的设置新建一个任务。':
    'Advertiser pages that came up when searching the library for "{k}", sorted by match score. If the wrong one was picked, click "Use this page" to start a new job with the same settings.',
  '主页': 'Page', '得分': 'Score', '识别依据': 'Matched on', '改抓这个主页': 'Use this page',
  // 任务页
  '总结': 'Summary', '素材库 ({n})': 'Library ({n})', '视频拆解 ({n})': 'Videos ({n})', '图片 ({n})': 'Images ({n})', '文案 ({n})': 'Copy ({n})',
  '店铺 ({n})': 'Advertisers ({n})', '商品与同款 ({n})': 'Products ({n})', '查询记录': 'Queries', '品牌主页': 'Brand page', '运行日志': 'Log',
  '快速': 'Quick', '标准': 'Standard', '深度': 'Deep', '{d}采集': '{d} depth', ' · AI 调用 {n} 次': ' · {n} AI calls',
  '取消': 'Cancel', 'AI 分析': 'AI analysis', '重新抓取': 'Re-run', '导出报告': 'Export report', '导出 CSV': 'Export CSV', '打开文件夹': 'Open folder', '删除': 'Delete',
  '提示和抓不到的内容': 'Notes and what could not be collected',
  // 详情
  '视频还没有下载。点“AI 拆解这条”会先下载、做分镜和转写。': 'The video is not downloaded yet. "AI analyze" will download it and build the storyboard and transcript first.',
  '没有素材画面': 'No media', '轮播/动态素材卡片（{n}）': 'Carousel / dynamic cards ({n})', '★ 已收藏': '★ Starred', '☆ 收藏': '☆ Star', '资料库↗': 'Library↗', '关闭 ✕': 'Close ✕',
  '视频数据': 'Video', '时长': 'Length', '{n} 秒': '{n}s', '镜头': 'Shots', '{n} 个，平均 {s}s 一个': '{n}, {s}s each on average', '切镜点': 'Cuts', '一镜到底': 'Single shot',
  '声音': 'Audio', '有音轨': 'Has audio', '无音轨': 'No audio', ' · 语言 {l}': ' · language {l}', '口播转写（点一行跳到那一秒）': 'Transcript (click a line to jump there)',
  '画面数据': 'Image', '投放数据': 'Delivery', '上线': 'Started', '（在投 {n} 天）': ' ({n} days running)', '同素材广告': 'Ads using it', '{n} 条': '{n}',
  '曝光排序': 'Impression rank', '第 {n}': '#{n}', '分类列表第 {n}': '#{n} in a filtered list', '不在前 30': 'Not in the top 30', '平台': 'Platforms',
  '命中查询': 'Found by', '达人合作': 'Creator partnership', '文案': 'Copy', '（无主文案）': '(no primary text)', '标题': 'Headline', '链接描述': 'Link description',
  '落地页': 'Landing page', '落地商品': 'Landing product', ' · 上架 {d}': ' · launched {d}', '开头': 'Opening', '{n} 行': '{n} lines', '{n} 个表情': '{n} emoji',
  ' · 最高 {n}% off': ' · up to {n}% off', 'AI 文案点评': 'AI copy review', '逐秒分镜（含切镜点）': 'Per-second storyboard (with cuts)', 'AI 拆解': 'AI breakdown',
  '还没有 AI 拆解。': 'No AI breakdown yet.', '重新 AI 拆解': 'Re-analyze with AI',
  // 提示框
  '设置里的分析引擎是“不做 AI 分析”，请先选择 Claude Code 或 Claude API': 'AI analysis is turned off in Settings. Choose Claude Code or Claude API first.',
  '分析引擎是 Claude API，请先填写 API key': 'The AI engine is Claude API. Enter an API key first.',
  '分析引擎是 Claude API，请先填写 API key；或者改用 Claude Code（用订阅，不需要 key）': 'The AI engine is Claude API. Enter an API key first, or switch to Claude Code (uses your subscription, no key needed).',
  '删除这个任务和它下载的所有素材？收藏的素材也会一起删除。': 'Delete this job and all its downloaded media? Its starred creatives will be removed too.',
  '已导出：{p}\n把整个任务文件夹打包，就能发给别人用浏览器打开（视频和图片都在 assets 文件夹里）。': 'Exported: {p}\nZip the whole job folder to share it; it opens in any browser (videos and images are in the assets folder).',
  '已导出：{p}\n可以直接用 Excel 打开。': 'Exported: {p}\nIt opens directly in Excel.',
  // 收藏夹
  '所有任务里收藏的素材，共 {n} 条。点素材打开它所在的任务和详情。': 'Starred creatives from every job ({n}). Click one to open its job and details.',
  '还没有收藏。在素材上点 ☆ 就能收藏。': 'Nothing starred yet. Click ☆ on any creative.',
  // 欢迎页
  '使用步骤': 'Getting started',
  '打开代理/VPN（要能访问 facebook.com）。Meta 广告资料库按你选的<b>投放国家</b>筛选，不需要把节点切到那个国家。':
    'Turn on a proxy / VPN if needed so facebook.com opens. The Ad Library filters by the <b>country</b> you choose, so your connection does not need to be in that country.',
  '点右上角“设置”，选择 AI 分析引擎：<b>Claude Code</b>（用你的 Claude 订阅，需先在终端运行 <code>claude</code> 并 <code>/login</code>）或 <b>Claude API</b>（填 API key）。不分析也能抓取，本地统计照样有。':
    'Click "Settings" (top right) and pick the AI engine: <b>Claude Code</b> (uses your Claude subscription; run <code>claude</code> and <code>/login</code> in a terminal once) or <b>Claude API</b> (enter an API key). Scraping and local stats work without AI.',
  '在左侧选<b>关键词模式</b>（输入英文产品词，例如 posture corrector）或<b>品牌模式</b>（输入品牌名或官网域名，例如 chewy.com），点“开始抓取”。标准深度大约 3–10 分钟，AI 分析另外 5–15 分钟。':
    'On the left, choose <b>Keyword mode</b> (an English product term, e.g. posture corrector) or <b>Brand mode</b> (a brand name or domain, e.g. chewy.com) and click "Start". Standard depth takes about 3–10 minutes, plus 5–15 minutes for AI analysis.',
  '看“总结”里的爆款素材和 AI 方案；在“素材库”里筛选、打开详情看视频分镜和口播；点 ☆ 收藏好素材，收藏夹跨任务汇总。':
    'Read the top creatives and AI concepts in "Summary"; filter the "Library" and open a creative for its storyboard and transcript; click ☆ to star creatives, collected across jobs in Favorites.',
  '检查中…': 'Checking…', '检查失败：': 'Check failed: ',
  // 设置
  'AI 分析引擎': 'AI engine', '需要先安装 Claude Code，并在终端运行 <code>claude</code> 后输入 <code>/login</code> 登录你的 Claude 订阅（Pro / Max）。分析会占用订阅额度。':
    'Install Claude Code first, then run <code>claude</code> in a terminal and type <code>/login</code> to sign in with your Claude subscription (Pro / Max). Analysis uses your subscription quota.',
  'Claude Code 使用的模型': 'Claude Code model', '只保存在本机 data/settings.json，不会上传。申请地址：console.anthropic.com': 'Stored only on this computer in data/settings.json. Get a key at console.anthropic.com',
  '分析模型': 'Model', '分析深度': 'Effort', '低（快、省）': 'Low (fast, cheap)', '中（推荐）': 'Medium (recommended)', '高（细、贵）': 'High (detailed, pricier)',
  '代理地址（可选）': 'Proxy (optional)', '例如 http://127.0.0.1:7890 ；留空使用系统代理': 'e.g. http://127.0.0.1:7890 ; leave empty to use the system proxy',
  '视频语音转写（口播文字 + 时间戳）': 'Transcribe videos (voice-over with timestamps)', '读取 Shopify 落地页的商品名、售价和原价': 'Read product title, price and compare-at price from Shopify pages',
  '抓取时显示浏览器窗口（遇到验证码时用）': 'Show the browser window while scraping (for CAPTCHAs)', '转写模型': 'Transcription model', '保存': 'Save',
  ' · Meta 素材侦察报告': ' · Meta ad report', '本地分析': 'Local analysis', '下载素材 · 分镜 · 转写': 'Media · storyboard · transcript', '落地页商品与价格': 'Landing products & prices', '采集广告资料库': 'Collect from Ad Library', '启动浏览器': 'Launch browser',
};
// 本地分析写进数据里的分类值（任务数据里存中文），显示时翻译
const EN_VAL = {
  '常青爆款': 'Evergreen winner', '新起量': 'Rising', '稳定在投': 'Steady', '在投': 'Active', '测试中': 'Testing',
  '折扣': 'Discount', '买赠/赠品': 'BOGO / gift', '包邮': 'Free shipping', '限时/稀缺': 'Urgency / scarcity', '社会证明': 'Social proof', '无风险保障': 'Risk-free guarantee',
  '痛点': 'Pain point', '专业背书': 'Authority', '前后对比': 'Before / after', '节日/送礼': 'Holiday / gifting', '价格锚点': 'Price anchor',
  '提问': 'Question', '数字开头': 'Starts with a number', '表情开头': 'Starts with an emoji', '痛点开头': 'Pain-point opener', '全大写': 'ALL CAPS', '感叹句': 'Exclamation', '陈述句': 'Statement',
  '短（≤125 字符）': 'Short (≤125 chars)', '中（126–400）': 'Medium (126–400)', '长（>400）': 'Long (>400)',
  '≤7 天': '≤7 days', '8–30 天': '8–30 days', '31–90 天': '31–90 days', '91–180 天': '91–180 days', '180 天以上': '180+ days',
  '偏暗': 'Dark', '明亮': 'Bright', '中等': 'Medium', '高饱和': 'saturated', '低饱和': 'muted',
  '快剪（平均 <1.5 秒一个镜头）': 'Fast cuts (<1.5s per shot)', '中等（1.5–3 秒）': 'Medium (1.5–3s per shot)', '慢节奏（>3 秒）': 'Slow (>3s per shot)', '无': 'None',
  '曝光最高 · 全部': 'Top impressions · all', '曝光最高 · 视频': 'Top impressions · video', '曝光最高 · 图片': 'Top impressions · image', '最新上线 · 全部': 'Newest · all',
  '最新上线 · 视频': 'Newest · video', '最新上线 · 图片': 'Newest · image', '曝光最高 · Instagram': 'Top impressions · Instagram', '曝光最高 · Facebook': 'Top impressions · Facebook',
  '最新上线 · Instagram': 'Newest · Instagram', '曝光最高 · 精确词组': 'Top impressions · exact phrase', '主页 · 曝光最高': 'Page · top impressions', '主页 · 最新上线': 'Page · newest',
  '主页 · 视频 · 曝光最高': 'Page · video · top impressions', '主页 · 图片 · 曝光最高': 'Page · image · top impressions', '主页 · 视频 · 最新': 'Page · video · newest',
  '主页 · 图片 · 最新': 'Page · image · newest', '主页 · 图文 · 曝光最高': 'Page · meme · top impressions', '主页 · Audience Network': 'Page · Audience Network',
  '主页 · Messenger': 'Page · Messenger', '主页 · 图文 · 最新': 'Page · meme · newest',
};
const t = (zh, vars) => {
  let s = LANG === 'en' ? (EN[zh] ?? zh) : zh;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => vars[k] ?? m);
  return s;
};
const tv = v => {  // 分类值
  if (LANG !== 'en' || v == null) return v;
  if (EN_VAL[v]) return EN_VAL[v];
  const s = String(v);
  if (s.startsWith('主页内搜索 · ')) return 'In-page search · ' + s.slice(7);
  if (s.includes('·')) return s.split('·').map(x => EN_VAL[x.trim()] ?? x.trim()).join(' · ');  // 色调：偏暗·高饱和
  return v;
};
const STATUS = {queued: '排队中', running: '抓取中', done: '完成', failed: '失败', cancelled: '已取消'};
const statusName = s => t(STATUS[s] || s);
const FORMAT_CN = {VIDEO: '视频', IMAGE: '图片', CAROUSEL: '轮播', DCO: '动态素材', DPA: '商品目录', MULTI_IMAGES: '多图', MULTI_VIDEOS: '多视频'};
const fmtName = f => t(FORMAT_CN[f] || f || '其他');
const listSep = () => LANG === 'en' ? ', ' : '、';

function applyStaticText() {
  // index.html 里固定的文字：第一次把中文原文记在 data-zh 上，之后按语言切换
  document.documentElement.lang = LANG === 'en' ? 'en' : 'zh-CN';
  $$('[data-i18n]').forEach(el => { el.dataset.zh ??= el.innerHTML.trim(); el.innerHTML = t(el.dataset.zh); });
  $$('[data-i18n-ph]').forEach(el => { el.dataset.zhPh ??= el.getAttribute('placeholder'); el.setAttribute('placeholder', t(el.dataset.zhPh)); });
  const b = $('#btnLang');
  if (b) { b.textContent = LANG === 'en' ? '中文' : 'EN'; b.title = LANG === 'en' ? '切换到中文' : 'Switch to English'; }
  if (!STATIC) document.title = t('Meta 素材侦察面板');
}
async function setLang(lang, save = true) {
  LANG = lang === 'en' ? 'en' : 'zh';
  try { localStorage.setItem('metaspy-lang', LANG); } catch (e) { /* 浏览器禁用存储时忽略 */ }
  applyStaticText();
  if (STATIC) { renderJob(); return; }
  if (save) await api('/api/settings', {method: 'POST', body: {lang: LANG}});
  await loadSettings();
  setMode(state.mode);
  loadJobs();
  if (state.view === 'job' && state.job) { renderJob(); if (state.drawer) renderDrawer(); }
  else if (state.view === 'starred') showStarred();
  else welcome();
}
$('#btnLang').onclick = () => setLang(LANG === 'en' ? 'zh' : 'en');

async function api(path, opts = {}) {
  const r = await fetch(path, {method: opts.method || 'GET', headers: {'Content-Type': 'application/json'}, body: opts.body ? JSON.stringify(opts.body) : undefined});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
const assetFor = (jid, p) => !p ? '' : (STATIC ? p : `/files/${encodeURIComponent(jid)}/${p}`);
const asset = p => assetFor(state.job?.id, p);
const ads = () => state.job?.results?.ads || [];
const findAd = id => ads().find(a => a.id === id) || (state.starred || []).find(a => a.id === id);

/* ---------------- 侧栏 ---------------- */
async function loadSettings() {
  state.settings = await api('/api/settings');
  const s = state.settings;
  $('#country').innerHTML = Object.entries(s.countries).map(([k, v]) => `<option value="${k}" ${k === s.country ? 'selected' : ''}>${esc(v)} (${k})</option>`).join('');
  $('#depth').value = s.depth; $('#maxVid').value = s.max_videos; $('#maxImg').value = s.max_images; $('#aiTop').value = s.ai_top_n;
  $('#optAnalyze').checked = !!s.auto_analyze;
}
async function loadJobs() {
  state.jobs = await api('/api/jobs');
  $('#jobs').innerHTML = state.jobs.length ? state.jobs.map(j => `<button class="jobitem ${j.id === state.cur ? 'on' : ''}" data-id="${esc(j.id)}">
      <span class="chip ${j.status}" style="float:right">${statusName(j.status)}</span>
      <b>${j.mode === 'brand' ? '🏷 ' : ''}${esc(j.keyword)}</b><small>${esc(j.createdAt.replace('T', ' ').slice(5, 16))} · ${esc(j.country)} · ${t('{n} 条素材', {n: j.ads})}${j.starred ? ` · ★${j.starred}` : ''}</small></button>`).join('')
    : `<div class="muted">${t('还没有任务')}</div>`;
  $$('.jobitem').forEach(b => b.onclick = () => { state.tab = 'summary'; state.f.page = ''; openJob(b.dataset.id); });
}
const MODE_UI = {
  keyword: {hint: '按产品词搜全网在投广告，看这个品类谁在投、怎么投。', ph: '产品词，例如 posture corrector\n多个词用逗号分隔（最多 5 个）',
    depth: ['快速（每个词 2 次查询，约 60 条）', '标准（每个词 6 次查询，约 120–180 条）', '深度（每个词 10 次查询，约 200–300 条）']},
  brand: {hint: '输入品牌名、官网域名或 Facebook 主页链接，自动识别官方主页，只抓这个主页的广告。', ph: '例如 chewy、chewy.com\n或 https://www.facebook.com/chewy',
    depth: ['快速（约 6 次查询，100–150 条）', '标准（约 18 次查询，250–400 条）', '深度（约 40 次查询，500–900 条）']},
};
state.mode = 'keyword';
function setMode(m) {
  state.mode = m;
  $$('.seg button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  const u = MODE_UI[m];
  $('#modeHint').textContent = t(u.hint); $('#kw').placeholder = t(u.ph);
  [...$('#depth').options].forEach((o, i) => { o.textContent = t(u.depth[i]); });
  $('#termsBox').style.display = m === 'brand' ? '' : 'none';
}
$$('.seg button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
$('#searchForm').onsubmit = async e => {
  e.preventDefault();
  const keyword = $('#kw').value.trim();
  if (!keyword) { $('#kw').focus(); return; }
  const options = {country: $('#country').value, depth: $('#depth').value, activeOnly: $('#optActive').checked, analyze: $('#optAnalyze').checked,
    maxVideos: +$('#maxVid').value, maxImages: +$('#maxImg').value, aiTopN: +$('#aiTop').value,
    mode: state.mode, terms: state.mode === 'brand' ? $('#terms').value : '', lang: LANG};
  try {
    const job = await api('/api/jobs', {method: 'POST', body: {keyword, options}});
    state.tab = 'summary';
    await loadJobs(); openJob(job.id);
  } catch (err) { alert(err.message); }
};

/* ---------------- 任务 ---------------- */
function busy(job) { return ['queued', 'running'].includes(job.status) || (job.results?.ads || []).some(a => ['queued', 'running'].includes(a.aiStatus)); }
async function openJob(id, quiet) {
  if (state.cur !== id) { state.sig = ''; state.limit = 60; }
  state.cur = id;
  state.view = 'job';
  clearTimeout(state.timer);
  let job;
  try { job = await api('/api/jobs/' + encodeURIComponent(id)); } catch (e) { $('#main').innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; }
  state.job = job;
  // 只有数据变了才重绘，避免打断正在看的视频和滚动位置
  const sig = JSON.stringify([job.status, job.current, (job.log || []).length, job.steps, (job.results?.ads || []).map(a => [a.aiStatus, a.aiMsg, !!a.analysis, !!a.starred])]);
  if (sig !== state.sig || !quiet) { state.sig = sig; renderJob(); if (state.drawer) renderDrawer(); }
  if (!quiet) loadJobs();
  if (busy(job)) state.timer = setTimeout(() => openJob(id, true).then(() => !busy(state.job) && loadJobs()), 3000);
}

function bars(obj, opts = {}) {
  const e = Object.entries(obj || {}).filter(([, v]) => v);
  if (!e.length) return `<div class="muted">${t('暂无数据')}</div>`;
  if (!opts.keep) e.sort((a, b) => b[1] - a[1]);
  const mx = Math.max(...e.map(x => x[1]));
  const lab = opts.label || tv;
  return e.slice(0, opts.n || 12).map(([k, v]) => `<div class="bar"><span title="${esc(lab(k))}">${esc(lab(k))}</span><div class="track"><div class="fill" style="width:${(v / mx * 100).toFixed(0)}%"></div></div><b>${v}</b></div>`).join('');
}
function weeks(obj) {
  const e = Object.entries(obj || {});
  if (!e.length) return `<div class="muted">${t('暂无数据')}</div>`;
  const mx = Math.max(...e.map(x => x[1]));
  return `<div class="weeks">${e.map(([k, v]) => `<div style="height:${Math.max(2, v / mx * 100)}%" title="${esc(t('{k} 这周：{v} 条', {k, v}))}"></div>`).join('')}</div>
    <div class="wlab"><span>${esc(e[0][0])}</span><span>${esc(e[e.length - 1][0])}</span></div>`;
}
const li = xs => (xs || []).map(x => `<li>${esc(x)}</li>`).join('');

function tile(a, jid) {
  const thumb = a.thumb ? `<img src="${assetFor(jid || state.job.id, a.thumb)}" alt="" loading="lazy">` : `<div class="noimg">${esc(a.mediaError || t('没有缩略图'))}</div>`;
  const dur = a.video?.seconds ? `${a.video.seconds}s` : (a.localImages?.length > 1 ? t('{n} 张', {n: a.localImages.length}) : '');
  return `<div class="tile" data-ad="${esc(a.id)}" ${jid ? `data-job="${esc(jid)}"` : ''} role="button" tabindex="0">
    <div class="ph">${thumb}<div class="badges"><span class="badge">${esc(fmtName(a.format))}${dur ? ' · ' + dur : ''}</span><span class="badge v-${esc(a.verdict)}">${esc(tv(a.verdict))}</span>${a.analysis ? '<span class="badge" style="background:#6b4fc8">AI</span>' : ''}</div>
      <span class="score" title="${t('爆款指数')}">${a.score}</span></div>
    <button class="star ${a.starred ? 'on' : ''}" data-star="${esc(a.id)}" ${jid ? `data-job="${esc(jid)}"` : ''} title="${a.starred ? t('取消收藏') : t('收藏')}">${a.starred ? '★' : '☆'}</button>
    <div class="tb"><div class="pg">${a.localAvatar ? `<img class="av" src="${assetFor(jid || state.job.id, a.localAvatar)}" alt="">` : ''}<span>${esc(a.pageName || '')}</span></div>
      <p>${esc(a.title || (a.body || '').split('\n')[0] || t('（无文案）'))}</p>
      <div class="nums"><span>${t('在投 {n} 天', {n: a.daysLive})}</span>${a.variants > 1 ? `<span>${t('{n} 条同素材', {n: a.variants})}</span>` : ''}${a.impRank ? `<span>${t('曝光第 {n}', {n: a.impRank})}</span>` : ''}${a.product?.price ? `<span>$${a.product.price}</span>` : ''}</div></div></div>`;
}

function renderSummary(job) {
  const r = job.results || {}, ins = r.insights || {}, s = r.summary, all = ads();
  if (!all.length) return `<div class="card empty">${job.status === 'running' || job.status === 'queued' ? t('采集中，请稍候…') : t('没有采集到广告（原因见上方提示）')}</div>`;
  const brand = job.options.mode === 'brand';
  const tot = Object.entries(r.totals || {}).map(([k, v]) => v).filter(v => v != null);
  const days = all.map(a => a.daysLive).sort((a, b) => a - b);
  const prices = ins.prices || [];
  const vids = all.filter(a => a.videos?.length).length;
  const stat = `<div class="stat">
    <div><b>${tot.length ? fmt(tot.reduce((a, b) => a + b, 0)) : '—'}</b><span>${brand ? t('主页在投广告总数') : t('资料库在投总数') + (tot.length > 1 ? t('（多个词相加）') : '')}</span></div>
    <div><b>${all.length}</b><span>${t('本次采集（去重后）')}</span></div>
    ${brand ? `<div><b>${tot.length && tot[0] ? Math.round(all.length / tot[0] * 100) + '%' : '—'}</b><span>${t('本次覆盖主页在投广告的比例')}</span></div>`
      : `<div><b>${(ins.advertisers || []).length}</b><span>${t('在投的店铺主页')}</span></div>`}
    <div><b>${(ins.verdicts || {})['常青爆款'] || 0} / ${(ins.verdicts || {})['新起量'] || 0}</b><span>${t('常青爆款 / 新起量')}</span></div>
    <div><b>${Math.round(vids / all.length * 100)}%</b><span>${t('视频素材占比')}</span></div>
    <div><b>${t('{n} 天', {n: days[Math.floor(days.length / 2)]})}</b><span>${t('在投天数中位数')}</span></div>
    <div><b>${ins.video?.medianSeconds ? ins.video.medianSeconds + 's' : '—'}</b><span>${t('视频时长中位数')}${ins.video?.medianShot ? t(' · 平均 {n}s 一个镜头', {n: ins.video.medianShot}) : ''}</span></div>
    <div><b>${prices.length ? prices[Math.floor(prices.length / 2)] : '—'}</b><span>${t('落地页售价中位数')}${prices.length ? t('（{n} 个商品，{a}–{b}；各店默认币种）', {n: prices.length, a: prices[0], b: prices[prices.length - 1]}) : ''}</span></div></div>`;
  const top = `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 10px;font-size:14.5px">${t('爆款指数最高的素材')} <span class="muted">${t('（在投天数 + 同素材广告数 + 曝光排序位置 + 平台数，Meta 不公开花费和点赞，这是用公开字段做的近似）')}</span></h3>
    <div class="tiles">${all.slice(0, 8).map(a => tile(a)).join('')}</div></div>`;
  const charts = `<div class="charts">
    <div class="card"><h3>${t('素材形式')}</h3>${bars(ins.formats, {label: fmtName})}</div>
    <div class="card"><h3>${t('投放状态判定')}</h3>${bars(ins.verdicts)}</div>
    <div class="card"><h3>${t('在投天数分布')}</h3>${bars(ins.daysLive, {keep: true})}</div>
    <div class="card"><h3>${t('近半年每周新上线（本次样本）')}</h3>${weeks(ins.weekly)}</div>
    <div class="card"><h3>${t('文案里的卖点/促销手法')}</h3>${bars(ins.tags)}</div>
    <div class="card"><h3>${t('文案开头类型')}</h3>${bars(ins.hookTypes)}</div>
    <div class="card"><h3>${t('文案长度')}</h3>${bars(ins.lengths)}</div>
    <div class="card"><h3>${t('CTA 按钮')}</h3>${bars(ins.ctas)}</div>
    ${ins.video ? `<div class="card"><h3>${t('视频时长（已拆解 {n} 条）', {n: ins.video.count})}</h3>${bars(ins.video.lengths, {keep: true})}<div class="muted" style="margin-top:8px">${esc(t('画幅：{a} · 有口播 {n} 条', {a: Object.entries(ins.video.aspects || {}).map(([k, v]) => `${k} ×${v}`).join(listSep()), n: ins.video.withVoice}))}</div></div>` : ''}
    ${ins.image ? `<div class="card"><h3>${t('图片画幅与色调（{n} 张）', {n: ins.image.count})}</h3>${bars(ins.image.aspects)}<div style="margin-top:8px">${bars(ins.image.tones, {n: 5})}</div></div>` : ''}
    <div class="card"><h3>${t('投放平台')}</h3>${bars(ins.platforms)}</div>
    <div class="card"><h3>${t('高频词组')} <span class="muted">${t('（按使用的店铺数）')}</span></h3><div class="chips">${(ins.phrases || []).slice(0, 24).map(p => `<span>${esc(p.text)}<i>${p.count}</i></span>`).join('') || `<span class="muted">${t('暂无')}</span>`}</div></div>
  </div>`;
  let ai = `<div class="card empty" style="margin-bottom:14px">${t('还没有 AI 总结。')}${esc(job.steps?.analysis?.msg || '')}</div>`;
  if (s) {
    ai = `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 6px">${brand ? t('品牌投放策略（AI）') : t('竞争格局（AI）')}</h3><div>${esc(s.overview)}</div>
        ${(s.products || []).length ? `<h3 style="margin:12px 0 6px;font-size:14px">${t('产品与价格带')}</h3><ul style="margin:0;padding-left:18px">${li(s.products)}</ul>` : ''}</div>
      <div class="summary">
        <div class="card"><h3>${t('关键发现')}</h3>${(s.signals || []).map(x => `<div class="signal"><b>${esc(x.title)}</b>${esc(x.body)}</div>`).join('')}</div>
        <div style="display:flex;flex-direction:column;gap:14px">
          <div class="card"><h3>${t('给你的素材建议')}</h3><ul>${li(s.recommendations)}</ul></div>
          <div class="card"><h3>${t('空白机会')}</h3><ul>${li(s.opportunities)}</ul></div>
          <div class="card"><h3>${t('跑得久的卖点角度')}</h3><ul>${li(s.winningAngles)}</ul></div>
          <div class="card"><h3>${t('优惠与价格策略')}</h3><ul>${li(s.offers)}</ul></div>
        </div></div>
      <div class="summary" style="margin-top:14px">
        <div class="card"><h3>${t('开头钩子套路')}</h3><ul>${li(s.hookPatterns)}</ul></div>
        <div class="card"><h3>${t('视频脚本与剪辑套路')}</h3><ul>${li(s.videoPatterns)}</ul></div>
        <div class="card"><h3>${t('图片画面套路')}</h3><ul>${li(s.visualPatterns)}</ul></div>
      </div>
      <h3 style="margin:20px 0 0">${t('可以直接拍的 3 个素材方案')}</h3>
      <div class="concepts">${(s.concepts || []).map(c => `<div class="card concept"><h4>${esc(c.name)}</h4><div class="muted">${esc(c.format)} · ${t('角度：')}${esc(c.angle)}</div>
        <div style="margin-top:6px"><b>${t('前 3 秒：')}</b>${esc(c.hook)}</div><ol>${li(c.outline)}</ol>
        <div class="pt"><b>Headline: </b>${esc(c.headline)}\n\n${esc(c.primaryText)}</div><div class="muted" style="margin-top:6px">${t('参考：')}${esc(c.reference)}</div></div>`).join('')}</div>`;
  }
  return stat + top + ai + `<h3 style="margin:22px 0 10px">${t('本地统计')}</h3>` + charts;
}

/* ---------------- 素材库 ---------------- */
function filtered(list) {
  const f = state.f, q = f.q.trim().toLowerCase();
  let xs = list.filter(a => (!f.format || (f.format === 'VIDEO' ? a.videos?.length : f.format === 'IMAGE' ? !a.videos?.length : a.format === f.format))
    && (!f.verdict || a.verdict === f.verdict) && (!f.page || (a.pageId || a.pageName) === f.page) && (!f.star || a.starred)
    && (!q || [a.body, a.title, a.pageName, a.linkUrl, a.linkDescription, a.video?.transcript?.text, a.analysis?.angle, a.copyReview?.angle].join(' ').toLowerCase().includes(q)));
  const by = {score: a => -a.score, days: a => -a.daysLive, variants: a => -(a.variants || 1), newest: a => a.daysLive, imp: a => a.impRank || 99,
    copy: a => -(a.copyReview?.score || 0)}[f.sort] || (a => -a.score);
  return xs.sort((a, b) => by(a) - by(b));
}
function renderLibrary() {
  const all = ads(), f = state.f;
  const list = filtered(all);
  const pageName = f.page ? (all.find(a => (a.pageId || a.pageName) === f.page)?.pageName || f.page) : '';
  return `<div class="filters">
      <input type="text" id="fQ" placeholder="${esc(t('搜索文案、店铺、落地页、口播…'))}" value="${esc(f.q)}">
      <select id="fFormat"><option value="">${t('全部形式')}</option><option value="VIDEO">${t('视频')}</option><option value="IMAGE">${t('图片类')}</option>
        ${[...new Set(all.map(a => a.format))].filter(Boolean).map(x => `<option value="${esc(x)}">${esc(fmtName(x))}</option>`).join('')}</select>
      <select id="fVerdict"><option value="">${t('全部判定')}</option>${['常青爆款', '新起量', '稳定在投', '在投', '测试中'].map(v => `<option value="${v}">${esc(tv(v))}</option>`).join('')}</select>
      <select id="fSort"><option value="score">${t('按爆款指数')}</option><option value="days">${t('按在投天数')}</option><option value="variants">${t('按同素材广告数')}</option>
        <option value="imp">${t('按曝光排序位置')}</option><option value="newest">${t('最新上线在前')}</option><option value="copy">${t('按 AI 文案分')}</option></select>
      <label class="noexport"><input type="checkbox" id="fStar" ${f.star ? 'checked' : ''}> ${t('只看收藏')}</label>
      <span class="muted">${t('{a} / {b} 条', {a: list.length, b: all.length})}</span></div>
    ${pageName ? `<div class="aibar" style="margin-bottom:12px">${t('只看店铺：')}<b>${esc(pageName)}</b><button class="btn sm" id="fClearPage">${t('清除')}</button></div>` : ''}
    ${list.length ? `<div class="tiles">${list.slice(0, state.limit).map(a => tile(a)).join('')}</div>` : `<div class="card empty">${t('没有符合条件的素材')}</div>`}
    ${list.length > state.limit ? `<button class="btn more" id="moreBtn">${t('再显示 {n} 条', {n: Math.min(60, list.length - state.limit)})}</button>` : ''}`;
}
function bindLibrary() {
  const f = state.f;
  const set = (id, k, ev = 'change') => { const el = $(id); if (!el) return; if (el.type !== 'checkbox') el.value = f[k]; el.addEventListener(ev, () => { f[k] = el.type === 'checkbox' ? el.checked : el.value; state.limit = 60; renderJob(k === 'q' ? '#fQ' : null); }); };
  set('#fQ', 'q', 'input'); set('#fFormat', 'format'); set('#fVerdict', 'verdict'); set('#fSort', 'sort'); set('#fStar', 'star');
  if ($('#fClearPage')) $('#fClearPage').onclick = () => { f.page = ''; renderJob(); };
  if ($('#moreBtn')) $('#moreBtn').onclick = () => { state.limit += 60; renderJob(); };
}

/* ---------------- 视频 / 图片 / 文案 ---------------- */
function analysisBlock(x, kind) {
  if (!x) return '';
  const shots = x.script?.length ? `<div class="tablewrap"><table class="shots"><thead><tr><th>${t('时间')}</th><th>${t('画面')}</th><th>${t('口播/声音')}</th><th>${t('作用')}</th></tr></thead><tbody>${
    x.script.map(s => `<tr><td>${esc(s.time)}</td><td>${esc(s.visual)}</td><td>${esc(s.audio || '—')}</td><td>${esc(s.purpose)}</td></tr>`).join('')}</tbody></table></div>` : '';
  return `<div class="an">
    <dl class="kv">${x.product ? `<dt>${t('产品')}</dt><dd>${esc(x.product)}</dd>` : ''}<dt>${t('形式')}</dt><dd>${esc(x.creativeType)}</dd><dt>${t('卖点角度')}</dt><dd><b>${esc(x.angle)}</b></dd>
      <dt>${t('钩子')}</dt><dd>${esc(x.hook)}</dd>${x.structure ? `<dt>${t('结构')}</dt><dd>${esc(x.structure)}</dd>` : ''}${x.pace ? `<dt>${t('节奏')}</dt><dd>${esc(x.pace)}</dd>` : ''}
      ${x.visual ? `<dt>${t('画面')}</dt><dd>${esc(x.visual)}</dd>` : ''}${x.textInImage ? `<dt>${t('图中文字')}</dt><dd>${esc(x.textInImage)}</dd>` : ''}<dt>${t('目标人群')}</dt><dd>${esc(x.audience)}</dd></dl>
    ${shots}
    <div class="box pros"><b>${t('优点')}</b><ul>${li(x.strengths)}</ul></div>
    <div class="box cons"><b>${t('可改良的空间')}</b><ul>${li(x.improvements)}</ul></div>
    <div class="box bor"><b>${t('我方可以直接借鉴')}</b>${esc(x.borrow)}</div>
    <div class="box rew"><b>${kind === 'video' ? t('改良脚本思路') : t('改写后的主文案')}</b>${esc(x.rewrite)}</div></div>`;
}
function copyReviewBlock(c) {
  if (!c) return '';
  return `<dl class="kv"><dt>${t('卖点角度')}</dt><dd>${esc(c.angle)}</dd><dt>${t('钩子类型')}</dt><dd>${esc(c.hookType)}</dd><dt>${t('文案结构')}</dt><dd>${esc(c.formula)}</dd>
    <dt>${t('优惠')}</dt><dd>${esc(c.offer)}</dd><dt>${t('文案力')}</dt><dd><b>${c.score}/10</b> · ${esc(c.note)}</dd></dl>`;
}
function renderVideos() {
  const vs = ads().filter(a => a.video);
  const rest = ads().filter(a => a.videos?.length && !a.video).length;
  if (!vs.length) return `<div class="card empty">${t('还没有拆解过的视频（在“素材数量”里调大“拆解视频”，或在素材详情里点“AI 拆解”）')}</div>`;
  return `<div class="muted" style="margin-bottom:10px">${t('已下载并拆解 {n} 条视频（按爆款指数）', {n: vs.length})}${rest ? t('；另有 {n} 条视频未下载，可在素材库里打开详情单独拆解', {n: rest}) : ''}${LANG === 'en' ? '.' : '。'}</div>
    <div class="vlist">${vs.map(a => {
    const v = a.video;
    return `<div class="card vcard"><div>
        ${a.localVideo ? `<video controls preload="none" style="width:100%;border-radius:12px;background:#000" poster="${asset(a.thumb)}" src="${asset(a.localVideo)}"></video>` : ''}
        <div class="nums muted" style="margin-top:6px">${v.seconds}s · ${esc(v.aspect || '')} · ${t('{n} 个镜头', {n: v.shots})} · ${esc(tv(v.pace) || '')}</div></div>
      <div style="display:flex;flex-direction:column;gap:8px;min-width:0">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b class="linkbtn" data-ad="${esc(a.id)}" role="button" tabindex="0">#${a.rank} ${esc(a.pageName)} · ${t('爆款指数')} ${a.score} · ${esc(tv(a.verdict))}</b>
          <span class="muted">${t('在投 {n} 天', {n: a.daysLive})}${a.variants > 1 ? ' · ' + t('{n} 条同素材', {n: a.variants}) : ''}</span></div>
        ${v.hookFrames ? `<div><div class="muted">${t('前 3 秒钩子帧')}</div><img class="sheet" src="${asset(v.hookFrames)}" alt="${esc(t('前 3 秒画面'))}" loading="lazy"></div>` : ''}
        ${v.transcript?.text ? `<div class="copy" style="max-height:110px;overflow:auto"><b>${t('口播：')}</b>${esc(v.transcript.text)}</div>` : `<div class="muted">${t('无口播（或只有背景音乐）')}</div>`}
        ${a.analysis ? `<details><summary style="cursor:pointer;color:var(--blue);font-weight:700">${t('AI 拆解：')}${esc(a.analysis.creativeType)} · ${esc(a.analysis.structure || '')}</summary>${analysisBlock(a.analysis, 'video')}</details>`
          : `<button class="btn sm noexport" data-aiad="${esc(a.id)}" style="align-self:flex-start">${a.aiStatus === 'running' || a.aiStatus === 'queued' ? esc(a.aiMsg) : t('AI 拆解这条')}</button>`}
      </div></div>`;
  }).join('')}</div>`;
}
function renderImages() {
  const xs = ads().filter(a => !a.videos?.length && a.imageInfo);
  if (!xs.length) return `<div class="card empty">${t('没有图片素材')}</div>`;
  return `<div class="tiles" style="grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr))">${xs.map(a => `<div class="card" style="padding:0;overflow:hidden">
      ${tile(a).replace('class="tile"', 'class="tile" style="border:0;box-shadow:none;border-radius:0"')}
      <div style="padding:0 12px 12px;display:flex;flex-direction:column;gap:6px">
        <div class="sw">${(a.imageInfo.colors || []).map(c => `<i style="background:${esc(c.hex)}" title="${esc(c.hex)} ${c.pct}%"></i>`).join('')}<span class="muted" style="margin-left:6px">${esc(a.imageInfo.aspect || '')} · ${esc(tv(a.imageInfo.tone) || '')}</span></div>
        ${a.analysis ? `<div style="font-size:13px"><b>${esc(a.analysis.creativeType)}</b> · ${esc(a.analysis.angle)}</div><div class="muted">${esc(a.analysis.hook)}</div>` : ''}
        ${a.analysis?.textInImage ? `<div class="muted"><b>${t('图中文字')}: </b>${esc(a.analysis.textInImage)}</div>` : ''}</div></div>`).join('')}</div>`;
}
function renderCopy() {
  const list = ads().filter(a => a.body || a.title);
  const sorted = [...list].sort((a, b) => state.copySort === 'ai' ? (b.copyReview?.score || 0) - (a.copyReview?.score || 0) : a.rank - b.rank);
  const reviewed = list.filter(a => a.copyReview).length;
  return `<div class="viewbar" style="display:flex;gap:6px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <button class="tab ${state.copySort !== 'ai' ? 'on' : ''}" data-csort="rank">${t('按爆款指数')}</button><button class="tab ${state.copySort === 'ai' ? 'on' : ''}" data-csort="ai">${t('按 AI 文案分')}</button>
      <span class="muted">${t('{n} 条有文案 · AI 点评 {m} 条', {n: list.length, m: reviewed})}</span></div>
    <div class="card pad tablewrap"><table class="list"><thead><tr><th>#</th><th>${t('店铺')}</th><th>${t('主文案')}</th><th>${t('标题 / CTA')}</th><th>${t('本地标签')}</th><th>${t('AI 角度 · 结构')}</th><th>${t('AI 分')}</th><th>${t('在投')}</th></tr></thead><tbody>${
    sorted.map(a => `<tr><td class="num"><button class="linkbtn" data-ad="${esc(a.id)}">${a.rank}</button></td><td>${esc(a.pageName)}</td>
      <td><div class="clip">${esc(a.body)}</div></td><td>${esc(a.title || '')}<div class="muted">${esc(a.cta || '')}${a.linkDescription ? ' · ' + esc(a.linkDescription) : ''}</div></td>
      <td><div class="tags">${(a.copy?.tags || []).map(x => `<span>${esc(tv(x))}</span>`).join('')}</div><div class="muted">${esc(tv(a.copy?.hookType) || '')} · ${t('{n} 字符', {n: a.copy?.chars || 0})}${a.copy?.emojis ? ' · ' + t('{n} 表情', {n: a.copy.emojis}) : ''}</div></td>
      <td>${a.copyReview ? `<b>${esc(a.copyReview.angle)}</b><div class="muted">${esc(a.copyReview.hookType)} · ${esc(a.copyReview.formula)}</div><div style="font-size:12.5px">${esc(a.copyReview.note)}</div>` : '<span class="muted">—</span>'}</td>
      <td class="num">${a.copyReview ? `<b>${a.copyReview.score}</b>` : '—'}</td><td class="num">${t('{n} 天', {n: a.daysLive})}</td></tr>`).join('')}</tbody></table></div>`;
}

/* ---------------- 店铺 / 商品 ---------------- */
function renderShops() {
  const xs = state.job.results?.insights?.advertisers || [];
  if (!xs.length) return `<div class="card empty">${t('暂无')}</div>`;
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">${t('点店铺名可以在素材库里只看这家店。“同素材”= 资料库里“N 条广告使用了这个素材和文案”的合计，越多说明在加预算铺量。')}</div>
    <table class="list"><thead><tr><th>${t('店铺主页')}</th><th>${t('粉丝')}</th><th>${t('素材数')}</th><th>${t('视频/图片')}</th><th>${t('最长在投')}</th><th>${t('中位在投')}</th><th>${t('同素材合计')}</th><th>${t('近 14 天新上')}</th><th>${t('最高爆款指数')}</th><th>${t('落地域名')}</th></tr></thead><tbody>${
    xs.map(p => `<tr><td><div style="display:flex;gap:8px;align-items:center">${p.avatar ? `<img class="av" style="width:28px;height:28px" src="${asset(p.avatar)}" alt="">` : ''}
        <div><button class="linkbtn" data-page="${esc(p.pageId)}">${esc(p.pageName)}</button>${p.pageUrl ? ` <a class="muted" href="${esc(p.pageUrl)}" target="_blank" rel="noopener">${t('主页↗')}</a>` : ''}
        <div class="muted">${esc((p.categories || []).join(listSep()))}</div></div></div></td>
      <td class="num">${fmt(p.likes)}</td><td class="num">${p.ads}</td><td class="num">${p.videos} / ${p.images}</td><td class="num">${t('{n} 天', {n: p.maxDays})}</td><td class="num">${t('{n} 天', {n: p.medianDays})}</td>
      <td class="num">${p.variants}</td><td class="num">${p.newLast14}</td><td class="num"><b>${p.bestScore}</b></td>
      <td>${(p.domains || []).map(d => esc(d)).join('<br>')}${p.shopify ? ' <span class="chip done">Shopify</span>' : ''}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderProducts() {
  const ins = state.job.results?.insights || {};
  const ps = ins.products || [];
  const disc = p => p.compareAt && p.price && p.compareAt > p.price ? `-${Math.round((1 - p.price / p.compareAt) * 100)}%` : '';
  const same = (ins.sameProduct || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">${t('同款竞争：同一个商品被多家店推')}</h3><table class="list"><thead><tr><th>${t('商品')}</th><th>${t('店铺')}</th><th>${t('广告数')}</th><th>${t('售价')}</th></tr></thead><tbody>${
    ins.sameProduct.map(g => `<tr><td><b>${esc(g.name)}</b></td><td>${g.shops.map(esc).join('<br>')}</td><td class="num">${g.ads}</td><td class="num">${g.prices.length ? g.prices.map(p => '$' + p).join(' / ') : '—'}</td></tr>`).join('')}</tbody></table></div>` : '';
  const sameCopy = (ins.sameCopy || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">${t('同一段文案被多个主页使用（铺货 / 同源素材）')}</h3><table class="list"><tbody>${
    ins.sameCopy.slice(0, 15).map(g => `<tr><td><div class="clip">${esc(g.snippet)}…</div></td><td>${g.pages.map(esc).join('<br>')}</td><td><button class="linkbtn" data-ad="${esc(g.adIds[0])}">${t('看素材')}</button></td></tr>`).join('')}</tbody></table></div>` : '';
  const sameCr = (ins.sameCreative || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">${t('同一张图/同一条视频被多个主页使用')}</h3><div class="tiles">${
    ins.sameCreative.slice(0, 12).map(g => `<div class="card" style="padding:8px"><img class="sheet" src="${asset(g.thumb)}" alt="" loading="lazy"><div class="muted" style="margin-top:6px">${g.pages.map(esc).join(listSep())}</div><button class="linkbtn" data-ad="${esc(g.adIds[0])}">${t('看素材')}</button></div>`).join('')}</div></div>` : '';
  return same + `<div class="card pad tablewrap" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">${t('落地商品（{n}）', {n: ps.length})}</h3>
    <div class="muted" style="margin-bottom:8px">${t('广告落地到 Shopify 商品页时，读取了公开的商品名、售价、原价和上架日期。价格是店铺默认币种。')}</div>
    <table class="list"><thead><tr><th></th><th>${t('商品')}</th><th>${t('店铺')}</th><th>${t('售价')}</th><th>${t('原价')}</th><th>${t('折扣')}</th><th>${t('上架')}</th><th>${t('广告数')}</th><th>${t('推广主页')}</th><th>${t('最长在投')}</th><th>${t('素材')}</th></tr></thead><tbody>${
    ps.map(p => `<tr><td>${p.image ? `<img class="pimg" src="${esc(p.image)}" alt="" loading="lazy">` : ''}</td><td><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>${p.variants ? `<div class="muted">${t('{n} 个规格', {n: p.variants})}</div>` : ''}</td>
      <td>${esc(p.domain)}</td><td class="num">${p.price ? '$' + p.price : '—'}</td><td class="num">${p.compareAt ? '$' + p.compareAt : '—'}</td><td class="num">${disc(p)}</td>
      <td class="num">${esc(p.createdAt || '—')}</td><td class="num">${p.ads}</td><td>${p.pages.map(esc).join('<br>')}</td><td class="num">${t('{n} 天', {n: p.maxDays})}</td>
      <td><button class="linkbtn" data-ad="${esc(p.adIds[0])}">${t('看素材')}</button></td></tr>`).join('')}</tbody></table></div>` + sameCopy + sameCr;
}
function renderQueries() {
  const qs = state.job.results?.queries || [];
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">${t('未登录时 Meta 每次只返回 30 条，所以用多组排序/筛选组合分别查询，再合并去重。点链接可以在浏览器里打开同样的资料库页面。')}</div>
    <table class="list"><thead><tr><th>${t('关键词')}</th><th>${t('查询')}</th><th>${t('资料库总数')}</th><th>${t('拿到')}</th><th>${t('新增')}</th><th>${t('链接')}</th></tr></thead><tbody>${
    qs.map(q => `<tr><td>${esc(q.keyword)}</td><td>${esc(tv(q.label))}</td><td class="num">${fmt(q.total)}</td><td class="num">${q.got}</td><td class="num">${q.new}</td>
      <td><a href="${esc(q.url)}" target="_blank" rel="noopener">${t('打开↗')}</a>${q.error ? `<div class="err">${esc(q.error)}</div>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
}

function brandCard(job) {
  const b = job.results?.brand;
  if (job.options.mode !== 'brand') return '';
  if (!b?.page) return `<div class="brandcard"><span>${esc(t('🏷 品牌模式：正在识别“{k}”的官方主页…', {k: job.keyword}))}</span></div>`;
  const p = b.page;
  const av = ads().find(a => a.pageId === p.pageId)?.localAvatar;
  return `<div class="brandcard">${av ? `<img src="${asset(av)}" alt="">` : ''}
    <div style="flex:1;min-width:200px"><div class="muted">${t('🏷 品牌模式 · 官方主页')}</div><b>${esc(p.pageName || p.pageId)}</b>
      ${p.pageUrl ? ` <a href="${esc(p.pageUrl)}" target="_blank" rel="noopener">${t('主页↗')}</a>` : ''}
      <div class="muted">${p.likes ? t('{n} 粉丝 · ', {n: fmt(p.likes)}) : ''}${t('主页在投 {a} 条 · 本次拿到 {b} 条', {a: fmt(p.pageTotal), b: ads().length})}${p.reasons?.length ? t(' · 识别依据：') + esc(p.reasons.join(listSep())) : ''}</div></div>
    ${b.candidates?.length > 1 ? `<button class="btn sm" data-tab-go="brand">${t('不是这个主页？')}</button>` : ''}</div>`;
}
function renderBrand() {
  const b = state.job.results?.brand;
  if (!b?.candidates?.length) return `<div class="card empty">${t('没有其他候选主页（主页是直接指定的）')}</div>`;
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">${esc(t('按“{k}”搜索资料库时出现的广告主页，按匹配得分排序。选错了就点“改抓这个主页”，会用同样的设置新建一个任务。', {k: b.input}))}</div>
    <table class="list"><thead><tr><th>${t('主页')}</th><th>${t('得分')}</th><th>${t('识别依据')}</th><th>${t('粉丝')}</th><th>${t('落地域名')}</th><th></th></tr></thead><tbody>${
    b.candidates.map(c => `<tr><td><b>${esc(c.pageName)}</b>${c.pageUrl ? ` <a class="muted" href="${esc(c.pageUrl)}" target="_blank" rel="noopener">${t('主页↗')}</a>` : ''}<div class="muted">ID ${esc(c.pageId)}</div></td>
      <td class="num"><b>${c.score}</b></td><td>${esc((c.reasons || []).join(listSep()) || '—')}</td><td class="num">${fmt(c.likes)}</td>
      <td>${esc(Object.keys(c.domains || {}).join(listSep()))}</td>
      <td>${c.pageId === b.page.pageId ? `<span class="chip done">${t('当前')}</span>` : `<button class="btn sm noexport" data-repage="${esc(c.pageId)}">${t('改抓这个主页')}</button>`}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderJob(focus) {
  const job = state.job, r = job.results || {}, steps = job.steps || {};
  const running = ['queued', 'running'].includes(job.status);
  const all = ads();
  const tabs = [['summary', t('总结')], ['library', t('素材库 ({n})', {n: all.length})], ['videos', t('视频拆解 ({n})', {n: all.filter(a => a.video).length})],
    ['images', t('图片 ({n})', {n: all.filter(a => !a.videos?.length && a.imageInfo).length})], ['copy', t('文案 ({n})', {n: all.filter(a => a.body || a.title).length})],
    ['shops', t('店铺 ({n})', {n: (r.insights?.advertisers || []).length})], ['products', t('商品与同款 ({n})', {n: (r.insights?.products || []).length})], ['queries', t('查询记录')]];
  if (job.options.mode === 'brand') tabs.splice(1, 0, ['brand', t('品牌主页')]);
  if (!STATIC) tabs.push(['log', t('运行日志')]);
  const body = {brand: renderBrand, library: renderLibrary, videos: renderVideos, images: renderImages, copy: renderCopy, shops: renderShops, products: renderProducts, queries: renderQueries,
    log: () => `<div class="log">${esc((job.log || []).join('\n'))}</div>`}[state.tab] || (() => renderSummary(job));
  const notices = job.notices || [];
  const depth = {quick: '快速', standard: '标准', deep: '深度'}[job.options.depth];
  $('#main').innerHTML = `<div class="card head">
      <div style="min-width:0"><h1>${esc(job.keyword)}</h1>
        <div class="meta">${esc(job.createdAt.replace('T', ' '))} · ${esc(state.settings?.countries?.[job.options.country] || job.options.country)} · ${depth ? esc(t('{d}采集', {d: t(depth)})) + ' · ' : ''}
          <span class="chip ${job.status}">${statusName(job.status)}</span>${running && job.current ? ' · ' + esc(job.current) : ''}${job.usage ? t(' · AI 调用 {n} 次', {n: job.usage.calls}) : ''}</div></div>
      <div class="btns">
        ${running ? `<button class="btn danger" data-act="cancel">${t('取消')}</button>` : `<button class="btn primary" data-act="analyze">${t('AI 分析')}</button><button class="btn" data-act="rerun">${t('重新抓取')}</button>`}
        <button class="btn" data-act="export" ${running ? 'disabled' : ''}>${t('导出报告')}</button><button class="btn" data-act="csv" ${running ? 'disabled' : ''}>${t('导出 CSV')}</button>
        <button class="btn" data-act="open">${t('打开文件夹')}</button>${running ? '' : `<button class="btn danger" data-act="delete">${t('删除')}</button>`}</div>
      <div class="steps">${Object.entries(steps).map(([k, s]) => `<div class="step ${s.status}"><b><span class="ico">${STEP_ICON[s.status] || ''}</span>${esc(STEP_LABEL[k] ? t(STEP_LABEL[k]) : s.label)}</b><div class="msg">${esc(s.msg || '')}</div></div>`).join('')}</div>
      ${brandCard(job)}
      ${notices.length ? `<div class="notices"><b>${t('提示和抓不到的内容')}</b><ul>${notices.map(n => `<li class="${n.level}"><b style="color:inherit">${esc(n.scope)}: </b>${esc(n.message)}</li>`).join('')}</ul></div>` : ''}
    </div>
    <div class="tabs">${tabs.map(([k, x]) => `<button class="tab ${state.tab === k ? 'on' : ''}" data-tab="${k}">${esc(x)}</button>`).join('')}</div>
    <div>${body()}</div>`;
  $$('[data-tab]').forEach(b => b.onclick = () => { state.tab = b.dataset.tab; renderJob(); });
  $$('[data-act]').forEach(b => b.onclick = () => jobAction(b.dataset.act));
  $$('[data-csort]').forEach(b => b.onclick = () => { state.copySort = b.dataset.csort; renderJob(); });
  $$('[data-page]').forEach(b => b.onclick = () => { state.f.page = b.dataset.page; state.tab = 'library'; renderJob(); });
  $$('[data-tab-go]').forEach(b => b.onclick = () => { state.tab = b.dataset.tabGo; renderJob(); });
  $$('[data-repage]').forEach(b => b.onclick = async () => {
    try { const r = await api(`/api/jobs/${encodeURIComponent(job.id)}/rerun`, {method: 'POST', body: {pageId: b.dataset.repage}}); state.tab = 'summary'; await loadJobs(); openJob(r.id); }
    catch (e) { alert(e.message); }
  });
  bindCommon($('#main'));
  if (state.tab === 'library') bindLibrary();
  if (focus && $(focus)) { const el = $(focus); el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
}
function bindCommon(root) {
  root.querySelectorAll('[data-ad]').forEach(el => {
    const open = e => { if (e.target.closest('[data-star]')) return; openDrawer(el.dataset.ad, el.dataset.job); };
    el.onclick = open;
    el.onkeydown = e => { if (e.key === 'Enter') open(e); };
  });
  root.querySelectorAll('[data-star]').forEach(b => b.onclick = e => { e.stopPropagation(); toggleStar(b.dataset.star, b.dataset.job); });
  root.querySelectorAll('[data-aiad]').forEach(b => b.onclick = e => { e.stopPropagation(); analyzeAd(b.dataset.aiad); });
}

async function toggleStar(id, jid) {
  if (STATIC) return;
  const job = jid || state.job.id;
  const a = jid ? (state.starred || []).find(x => x.id === id) : findAd(id);
  const on = !a?.starred;
  try {
    await api(`/api/jobs/${encodeURIComponent(job)}/star`, {method: 'POST', body: {adId: id, on}});
    if (a) a.starred = on;
    if (jid) { showStarred(); } else { state.sig = ''; await openJob(state.job.id, true); }
    if (state.drawer) renderDrawer();
    loadJobs();
  } catch (e) { alert(e.message); }
}
async function analyzeAd(id) {
  const s = state.settings || {};
  if (s.engine === 'none') { alert(t('设置里的分析引擎是“不做 AI 分析”，请先选择 Claude Code 或 Claude API')); openSettings(); return; }
  if (s.engine === 'api' && !s.has_api_key) { alert(t('分析引擎是 Claude API，请先填写 API key')); openSettings(); return; }
  try { await api(`/api/jobs/${encodeURIComponent(state.job.id)}/analyzead`, {method: 'POST', body: {adId: id}}); state.sig = ''; openJob(state.job.id, true); }
  catch (e) { alert(e.message); }
}

/* ---------------- 素材详情抽屉 ---------------- */
async function openDrawer(id, jid) {
  if (jid && jid !== state.job?.id) { closeDrawer(); state.tab = 'library'; await openJob(jid); }
  state.drawer = id;
  renderDrawer();
  $('#drawer').classList.add('on');
}
function closeDrawer() { state.drawer = null; $('#drawer').classList.remove('on'); $('#drawerPanel').innerHTML = ''; }
$('#drawer').onclick = e => { if (e.target.id === 'drawer') closeDrawer(); };
document.addEventListener('keydown', e => { if (e.key === 'Escape' && state.drawer) closeDrawer(); });
function renderDrawer() {
  const a = ads().find(x => x.id === state.drawer);
  if (!a) return;
  const v = a.video, p = a.product, ii = a.imageInfo, c = a.copy || {};
  const keepTime = $('#dVideo')?.currentTime;
  const media = a.localVideo ? `<div class="player"><video id="dVideo" controls playsinline preload="metadata" poster="${asset(a.thumb)}" src="${asset(a.localVideo)}"></video></div>`
    : a.localImages?.length ? `<div class="gal">${a.localImages.map(x => `<a href="${asset(x)}" target="_blank" rel="noopener"><img src="${asset(x)}" alt=""></a>`).join('')}</div>`
    : a.thumb ? `<img class="sheet" src="${asset(a.thumb)}" alt="">${a.videos?.length ? `<div class="muted" style="margin-top:6px">${t('视频还没有下载。点“AI 拆解这条”会先下载、做分镜和转写。')}</div>` : ''}` : `<div class="muted">${t('没有素材画面')}</div>`;
  const cards = a.cards?.length > 1 ? `<div class="card"><h4>${t('轮播/动态素材卡片（{n}）', {n: a.cards.length})}</h4>${a.cards.map((x, i) => `<div style="margin-bottom:6px;font-size:13px"><b>${i + 1}. ${esc(x.title || '')}</b> <span class="muted">${esc(x.cta || '')}</span>${x.body && x.body !== a.body ? `<div class="muted">${esc(x.body.slice(0, 200))}</div>` : ''}</div>`).join('')}</div>` : '';
  const aiStatus = ['queued', 'running'].includes(a.aiStatus) ? `<div class="aibar">◐ ${esc(a.aiMsg)}</div>` : a.aiStatus === 'failed' ? `<div class="aibar" style="background:var(--coral-soft)">✕ ${esc(a.aiMsg)}</div>` : '';
  const rank = a.impRank ? t('第 {n}', {n: a.impRank}) : (a.impRankOther ? t('分类列表第 {n}', {n: a.impRankOther}) : t('不在前 30'));
  $('#drawerPanel').innerHTML = `<div class="dhead"><b>#${a.rank} ${esc(a.pageName)} · ${esc(fmtName(a.format))}</b>
      <div style="display:flex;gap:6px;flex:none">${STATIC ? '' : `<button class="btn sm" id="dStar">${a.starred ? t('★ 已收藏') : t('☆ 收藏')}</button>`}
        <a class="btn sm" style="text-decoration:none" href="${esc(a.libraryUrl)}" target="_blank" rel="noopener">${t('资料库↗')}</a><button class="btn sm" id="dClose">${t('关闭 ✕')}</button></div></div>
    <div class="dbody"><div>
      <div class="card">${media}</div>
      ${v ? `<div class="card"><h4>${t('视频数据')}</h4><dl class="kv"><dt>${t('时长')}</dt><dd>${t('{n} 秒', {n: v.seconds})} · ${esc(v.aspect || '')}</dd><dt>${t('镜头')}</dt><dd>${t('{n} 个，平均 {s}s 一个', {n: v.shots, s: v.avgShot})} · ${esc(tv(v.pace) || '')}</dd>
          <dt>${t('切镜点')}</dt><dd>${(v.cuts || []).map(x => `<button class="linkbtn" data-seek="${x}">${x}s</button>`).join(' ') || t('一镜到底')}</dd><dt>${t('声音')}</dt><dd>${v.hasAudio ? t('有音轨') : t('无音轨')}${v.transcript?.lang ? t(' · 语言 {l}', {l: esc(v.transcript.lang)}) : ''}</dd></dl>
        ${v.transcript?.segments?.length ? `<h4 style="margin-top:10px">${t('口播转写（点一行跳到那一秒）')}</h4><div class="trs">${v.transcript.segments.map(s => `<button data-seek="${s.t}"><i>${s.t}s</i>${esc(s.text)}</button>`).join('')}</div>`
          : v.transcript?.error ? `<div class="err">${esc(v.transcript.error)}</div>` : ''}</div>` : ''}
      ${ii ? `<div class="card"><h4>${t('画面数据')}</h4><div class="sw">${(ii.colors || []).map(x => `<i style="background:${esc(x.hex)}" title="${esc(x.hex)} ${x.pct}%"></i>`).join('')}</div>
          <div class="muted" style="margin-top:6px">${ii.w}×${ii.h} · ${esc(ii.aspect || '')} · ${esc(tv(ii.tone) || '')}</div></div>` : ''}
      <div class="card"><h4>${t('投放数据')}</h4><dl class="kv"><dt>${t('爆款指数')}</dt><dd><b>${a.score}</b> · ${esc(tv(a.verdict))}</dd><dt>${t('上线')}</dt><dd>${esc(a.startDate)}${t('（在投 {n} 天）', {n: a.daysLive})}</dd>
        <dt>${t('同素材广告')}</dt><dd>${t('{n} 条', {n: a.variants})}</dd><dt>${t('曝光排序')}</dt><dd>${rank}</dd>
        <dt>${t('平台')}</dt><dd>${esc((a.platforms || []).join(listSep()))}</dd><dt>${t('命中查询')}</dt><dd>${esc((a.hits || []).map(tv).join(LANG === 'en' ? '; ' : '；'))}</dd>
        <dt>${t('主页')}</dt><dd>${a.pageUrl ? `<a href="${esc(a.pageUrl)}" target="_blank" rel="noopener">${esc(a.pageName)}</a>` : esc(a.pageName)}${a.pageLikes ? ' · ' + t('{n} 粉丝 · ', {n: fmt(a.pageLikes)}).replace(/ · $/, '') : ''}</dd>
        ${a.creatorPage ? `<dt>${t('达人合作')}</dt><dd>${esc(a.creatorPage)}</dd>` : ''}</dl></div>
    </div><div>
      ${aiStatus}
      <div class="card"><h4>${t('文案')}</h4><div class="copy">${esc(a.body || t('（无主文案）'))}</div>
        <dl class="kv" style="margin-top:10px"><dt>${t('标题')}</dt><dd>${esc(a.title || '—')}</dd><dt>${t('链接描述')}</dt><dd>${esc(a.linkDescription || '—')}</dd><dt>CTA</dt><dd>${esc(a.cta || '—')}</dd>
          <dt>${t('落地页')}</dt><dd>${a.linkUrl ? `<a href="${esc(a.linkUrl)}" target="_blank" rel="noopener">${esc(a.linkUrl)}</a>` : '—'}${a.shopPlatform ? ' <span class="chip done">Shopify</span>' : ''}</dd>
          ${p ? `<dt>${t('落地商品')}</dt><dd><b>${esc(p.title)}</b> · $${p.price}${p.compareAt ? ` <s class="muted">$${p.compareAt}</s>` : ''}${p.createdAt ? esc(t(' · 上架 {d}', {d: p.createdAt})) : ''}</dd>` : ''}
          <dt>${t('本地标签')}</dt><dd><div class="tags">${(c.tags || []).map(x => `<span>${esc(tv(x))}</span>`).join('') || '—'}</div></dd>
          <dt>${t('开头')}</dt><dd>${esc(tv(c.hookType) || '')} · ${t('{n} 字符', {n: c.chars || 0})} · ${t('{n} 行', {n: c.lines || 0})}${c.emojis ? ' · ' + t('{n} 个表情', {n: c.emojis}) : ''}${c.maxPctOff ? t(' · 最高 {n}% off', {n: c.maxPctOff}) : ''}</dd></dl>
        ${a.copyReview ? `<h4 style="margin-top:12px">${t('AI 文案点评')}</h4>${copyReviewBlock(a.copyReview)}` : ''}</div>
      ${cards}
      ${v?.hookFrames ? `<div class="card"><h4>${t('前 3 秒钩子帧')}</h4><img class="sheet" src="${asset(v.hookFrames)}" alt=""></div>` : ''}
      ${v?.storyboard ? `<div class="card"><h4>${t('逐秒分镜（含切镜点）')}</h4><a href="${asset(v.storyboard)}" target="_blank" rel="noopener"><img class="sheet" src="${asset(v.storyboard)}" alt=""></a></div>` : ''}
      <div class="card"><h4>${t('AI 拆解')}</h4>${a.analysis ? analysisBlock(a.analysis, a.analysis.kind) : `<div class="muted" style="margin-bottom:8px">${t('还没有 AI 拆解。')}</div>`}
        ${STATIC ? '' : `<button class="btn primary sm" style="margin-top:10px" id="dAi" ${['queued', 'running'].includes(a.aiStatus) || ['queued', 'running'].includes(state.job.status) ? 'disabled' : ''}>${a.analysis ? t('重新 AI 拆解') : t('AI 拆解这条')}</button>`}</div>
    </div></div>`;
  $('#dClose').onclick = closeDrawer;
  if ($('#dStar')) $('#dStar').onclick = () => toggleStar(a.id);
  if ($('#dAi')) $('#dAi').onclick = () => { if (a.analysis) a.analysis = null; analyzeAd(a.id); };
  const vid = $('#dVideo');
  if (vid && keepTime) vid.currentTime = keepTime;
  $$('#drawerPanel [data-seek]').forEach(b => b.onclick = () => { const el = $('#dVideo'); if (el) { el.currentTime = +b.dataset.seek; el.play().catch(() => {}); } });
}

/* ---------------- 任务操作 ---------------- */
async function jobAction(act) {
  const id = state.job.id;
  if (act === 'delete' && !confirm(t('删除这个任务和它下载的所有素材？收藏的素材也会一起删除。'))) return;
  if (act === 'analyze') {
    const s = state.settings || {};
    if (s.engine === 'none') { alert(t('设置里的分析引擎是“不做 AI 分析”，请先选择 Claude Code 或 Claude API')); openSettings(); return; }
    if (s.engine === 'api' && !s.has_api_key) { alert(t('分析引擎是 Claude API，请先填写 API key；或者改用 Claude Code（用订阅，不需要 key）')); openSettings(); return; }
  }
  try {
    const r = await api(`/api/jobs/${encodeURIComponent(id)}/${act}`, {method: 'POST'});
    if (act === 'delete') { state.cur = null; state.job = null; closeDrawer(); await loadJobs(); welcome(); return; }
    if (act === 'rerun') { state.tab = 'summary'; await loadJobs(); openJob(r.id); return; }
    if (act === 'export') alert(t('已导出：{p}\n把整个任务文件夹打包，就能发给别人用浏览器打开（视频和图片都在 assets 文件夹里）。', {p: r.path}));
    if (act === 'csv') { alert(t('已导出：{p}\n可以直接用 Excel 打开。', {p: r.path})); return; }
    state.sig = ''; openJob(id);
  } catch (e) { alert(e.message); }
}

/* ---------------- 收藏夹 ---------------- */
async function showStarred() {
  clearTimeout(state.timer);
  state.cur = null; state.view = 'starred'; loadJobs();
  try { state.starred = await api('/api/starred'); } catch (e) { $('#main').innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; }
  const xs = state.starred;
  $('#main').innerHTML = `<div class="card head"><div><h1>${t('★ 收藏夹')}</h1><div class="meta">${t('所有任务里收藏的素材，共 {n} 条。点素材打开它所在的任务和详情。', {n: xs.length})}</div></div></div>
    <div style="margin-top:14px">${xs.length ? `<div class="tiles">${xs.map(a => tile(a, a.jobId).replace('<div class="tb">', `<div class="tb"><span class="muted">${esc(a.jobKeyword)}</span>`)).join('')}</div>`
      : `<div class="card empty">${t('还没有收藏。在素材上点 ☆ 就能收藏。')}</div>`}</div>`;
  bindCommon($('#main'));
}
$('#btnStarred').onclick = showStarred;

/* ---------------- 欢迎页 / 环境检查 / 设置 ---------------- */
async function welcome() {
  state.view = 'welcome';
  $('#main').innerHTML = `<div class="card welcome"><h2>${t('使用步骤')}</h2><ol>
    <li>${t('打开代理/VPN（要能访问 facebook.com）。Meta 广告资料库按你选的<b>投放国家</b>筛选，不需要把节点切到那个国家。')}</li>
    <li>${t('点右上角“设置”，选择 AI 分析引擎：<b>Claude Code</b>（用你的 Claude 订阅，需先在终端运行 <code>claude</code> 并 <code>/login</code>）或 <b>Claude API</b>（填 API key）。不分析也能抓取，本地统计照样有。')}</li>
    <li>${t('在左侧选<b>关键词模式</b>（输入英文产品词，例如 posture corrector）或<b>品牌模式</b>（输入品牌名或官网域名，例如 chewy.com），点“开始抓取”。标准深度大约 3–10 分钟，AI 分析另外 5–15 分钟。')}</li>
    <li>${t('看“总结”里的爆款素材和 AI 方案；在“素材库”里筛选、打开详情看视频分镜和口播；点 ☆ 收藏好素材，收藏夹跨任务汇总。')}</li></ol>
    <h2 style="margin-top:22px">${t('环境检查')}</h2><div id="checkBox" class="muted">${t('检查中…')}</div></div>`;
  runCheck();
}
async function runCheck() {
  try {
    const rows = await api('/api/check?refresh=1');
    const box = $('#checkBox');
    if (box) box.outerHTML = `<div class="check">${rows.map(r => `<span class="${r.ok ? 'ok' : 'no'}">${r.ok ? '✓' : '✕'} ${esc(r.name)}</span><span>${esc(r.detail)}</span>`).join('')}</div>`;
  } catch (e) { const box = $('#checkBox'); if (box) box.textContent = t('检查失败：') + e.message; }
}
function syncEngineBoxes() {
  const e = $('#sEngine').value;
  $('#ccBox').style.display = e === 'claude_code' ? '' : 'none';
  $('#apiBox').style.display = e === 'api' ? '' : 'none';
}
function openSettings() {
  const s = state.settings;
  const opts = (o, cur) => Object.entries(o).map(([k, v]) => `<option value="${k}" ${k === cur ? 'selected' : ''}>${esc(v)}</option>`).join('');
  $('#sEngine').innerHTML = opts(s.engines, s.engine); $('#sCcModel').innerHTML = opts(s.cc_models, s.cc_model);
  $('#sModel').innerHTML = opts(s.models, s.model); $('#sWhisper').innerHTML = opts(s.whisper_models, s.whisper_model);
  $('#sEngine').onchange = syncEngineBoxes; syncEngineBoxes();
  $('#sKey').value = s.api_key || ''; $('#sEffort').value = s.effort; $('#sProxy').value = s.proxy || '';
  $('#sTranscribe').checked = !!s.transcribe; $('#sShop').checked = !!s.shop_enrich; $('#sShow').checked = !!s.show_browser;
  $('#settingsModal').classList.add('on');
}
$('#btnSettings').onclick = openSettings;
$('#sCancel').onclick = () => $('#settingsModal').classList.remove('on');
$('#sSave').onclick = async () => {
  await api('/api/settings', {method: 'POST', body: {engine: $('#sEngine').value, cc_model: $('#sCcModel').value, api_key: $('#sKey').value.trim(),
    model: $('#sModel').value, effort: $('#sEffort').value, proxy: $('#sProxy').value.trim(), transcribe: $('#sTranscribe').checked,
    shop_enrich: $('#sShop').checked, show_browser: $('#sShow').checked, whisper_model: $('#sWhisper').value}});
  await loadSettings();
  $('#settingsModal').classList.remove('on');
};
$('#btnCheck').onclick = () => { state.cur = null; clearTimeout(state.timer); loadJobs(); welcome(); };

/* ---------------- 署名水印（作者要求保留，请勿删除或修改） ---------------- */
const WATERMARK_HTML = 'made by <a href="https://yestupa.com" target="_blank" rel="noopener">yestupa.com</a>/<a href="https://yestupa.net" target="_blank" rel="noopener">yestupa.net</a> with ❤️';
const WATERMARK_TEXT = 'made by yestupa.com/yestupa.net with ❤️';
function ensureWatermark() {
  let f = document.getElementById('yestupa-wm');
  if (!f || f.textContent.replace(/\s+/g, ' ').trim() !== WATERMARK_TEXT || getComputedStyle(f).display === 'none' || getComputedStyle(f).visibility === 'hidden') {
    if (f) f.remove();
    f = document.createElement('footer');
    f.id = 'yestupa-wm';
    f.className = 'wm';
    f.innerHTML = WATERMARK_HTML;
    document.body.appendChild(f);
  }
}
ensureWatermark();
new MutationObserver(() => ensureWatermark()).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'hidden']});
setInterval(ensureWatermark, 3000);

/* ---------------- 启动 ---------------- */
function storedLang() {
  try { return localStorage.getItem('metaspy-lang'); } catch (e) { return null; }
}
const browserLang = () => /^zh/i.test(navigator.language || '') ? 'zh' : 'en';
if (STATIC) {
  document.body.classList.add('static');
  state.job = STATIC;
  state.view = 'job';
  state.settings = {countries: {}};
  LANG = storedLang() || STATIC.options?.lang || 'zh';
  applyStaticText();
  document.title = STATIC.keyword + t(' · Meta 素材侦察报告');
  renderJob();
} else {
  loadSettings().then(async () => {
    const s = state.settings;
    LANG = s.lang === 'en' || s.lang === 'zh' ? s.lang : (storedLang() || browserLang());
    if (!s.lang) await api('/api/settings', {method: 'POST', body: {lang: LANG}}).then(loadSettings);  // 第一次打开：记住自动选的语言
    applyStaticText();
    setMode('keyword');
    await loadJobs();
    state.jobs[0] ? openJob(state.jobs[0].id) : welcome();
  });
}
