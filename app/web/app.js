/* Meta 素材侦察面板：前端逻辑。导出的静态报告也用这份代码（window.STATIC_JOB 存在时为静态模式）。 */
const STATIC = window.STATIC_JOB || null;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmt = n => n == null ? '—' : Number(n).toLocaleString();
const state = {settings: null, jobs: [], cur: null, job: null, tab: 'summary', timer: null, sig: '', f: {q: '', format: '', verdict: '', sort: 'score', page: '', star: false}, limit: 60, drawer: null, starred: null};
const STEP_ICON = {pending: '○', running: '◐', done: '✓', failed: '✕', skipped: '–'};
const STATUS_CN = {queued: '排队中', running: '抓取中', done: '完成', failed: '失败', cancelled: '已取消'};
const FORMAT_CN = {VIDEO: '视频', IMAGE: '图片', CAROUSEL: '轮播', DCO: '动态素材', DPA: '商品目录', MULTI_IMAGES: '多图', MULTI_VIDEOS: '多视频'};
const fmtName = f => FORMAT_CN[f] || f || '其他';

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
  $('#country').innerHTML = Object.entries(s.countries).map(([k, v]) => `<option value="${k}" ${k === s.country ? 'selected' : ''}>${esc(v)}（${k}）</option>`).join('');
  $('#depth').value = s.depth; $('#maxVid').value = s.max_videos; $('#maxImg').value = s.max_images; $('#aiTop').value = s.ai_top_n;
  $('#optAnalyze').checked = !!s.auto_analyze;
}
async function loadJobs() {
  state.jobs = await api('/api/jobs');
  $('#jobs').innerHTML = state.jobs.length ? state.jobs.map(j => `<button class="jobitem ${j.id === state.cur ? 'on' : ''}" data-id="${esc(j.id)}">
      <span class="chip ${j.status}" style="float:right">${STATUS_CN[j.status] || j.status}</span>
      <b>${j.mode === 'brand' ? '🏷 ' : ''}${esc(j.keyword)}</b><small>${esc(j.createdAt.replace('T', ' ').slice(5, 16))} · ${esc(j.country)} · ${j.ads} 条素材${j.starred ? ` · ★${j.starred}` : ''}</small></button>`).join('')
    : '<div class="muted">还没有任务</div>';
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
  $('#modeHint').textContent = u.hint; $('#kw').placeholder = u.ph;
  [...$('#depth').options].forEach((o, i) => { o.textContent = u.depth[i]; });
  $('#termsBox').style.display = m === 'brand' ? '' : 'none';
}
$$('.seg button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
$('#searchForm').onsubmit = async e => {
  e.preventDefault();
  const keyword = $('#kw').value.trim();
  if (!keyword) { $('#kw').focus(); return; }
  const options = {country: $('#country').value, depth: $('#depth').value, activeOnly: $('#optActive').checked, analyze: $('#optAnalyze').checked,
    maxVideos: +$('#maxVid').value, maxImages: +$('#maxImg').value, aiTopN: +$('#aiTop').value,
    mode: state.mode, terms: state.mode === 'brand' ? $('#terms').value : ''};
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
  if (!e.length) return '<div class="muted">暂无数据</div>';
  if (!opts.keep) e.sort((a, b) => b[1] - a[1]);
  const mx = Math.max(...e.map(x => x[1]));
  return e.slice(0, opts.n || 12).map(([k, v]) => `<div class="bar"><span title="${esc(k)}">${esc(opts.label ? opts.label(k) : k)}</span><div class="track"><div class="fill" style="width:${(v / mx * 100).toFixed(0)}%"></div></div><b>${v}</b></div>`).join('');
}
function weeks(obj) {
  const e = Object.entries(obj || {});
  if (!e.length) return '<div class="muted">暂无数据</div>';
  const mx = Math.max(...e.map(x => x[1]));
  return `<div class="weeks">${e.map(([k, v]) => `<div style="height:${Math.max(2, v / mx * 100)}%" title="${esc(k)} 这周：${v} 条"></div>`).join('')}</div>
    <div class="wlab"><span>${esc(e[0][0])}</span><span>${esc(e[e.length - 1][0])}</span></div>`;
}
const li = xs => (xs || []).map(x => `<li>${esc(x)}</li>`).join('');

function tile(a, jid) {
  const thumb = a.thumb ? `<img src="${assetFor(jid || state.job.id, a.thumb)}" alt="" loading="lazy">` : `<div class="noimg">${esc(a.mediaError || '没有缩略图')}</div>`;
  const dur = a.video?.seconds ? `${a.video.seconds}s` : (a.localImages?.length > 1 ? `${a.localImages.length} 张` : '');
  return `<div class="tile" data-ad="${esc(a.id)}" ${jid ? `data-job="${esc(jid)}"` : ''} role="button" tabindex="0">
    <div class="ph">${thumb}<div class="badges"><span class="badge">${esc(fmtName(a.format))}${dur ? ' · ' + dur : ''}</span><span class="badge v-${esc(a.verdict)}">${esc(a.verdict)}</span>${a.analysis ? '<span class="badge" style="background:#6b4fc8">AI</span>' : ''}</div>
      <span class="score" title="爆款指数">${a.score}</span></div>
    <button class="star ${a.starred ? 'on' : ''}" data-star="${esc(a.id)}" ${jid ? `data-job="${esc(jid)}"` : ''} title="${a.starred ? '取消收藏' : '收藏'}">${a.starred ? '★' : '☆'}</button>
    <div class="tb"><div class="pg">${a.localAvatar ? `<img class="av" src="${assetFor(jid || state.job.id, a.localAvatar)}" alt="">` : ''}<span>${esc(a.pageName || '')}</span></div>
      <p>${esc(a.title || (a.body || '').split('\n')[0] || '（无文案）')}</p>
      <div class="nums"><span>在投 ${a.daysLive} 天</span>${a.variants > 1 ? `<span>${a.variants} 条同素材</span>` : ''}${a.impRank ? `<span>曝光第 ${a.impRank}</span>` : ''}${a.product?.price ? `<span>$${a.product.price}</span>` : ''}</div></div></div>`;
}

function renderSummary(job) {
  const r = job.results || {}, ins = r.insights || {}, s = r.summary, all = ads();
  if (!all.length) return `<div class="card empty">${job.status === 'running' || job.status === 'queued' ? '采集中，请稍候…' : '没有采集到广告（原因见上方提示）'}</div>`;
  const tot = Object.entries(r.totals || {}).map(([k, v]) => v).filter(v => v != null);
  const days = all.map(a => a.daysLive).sort((a, b) => a - b);
  const prices = ins.prices || [];
  const vids = all.filter(a => a.videos?.length).length;
  const stat = `<div class="stat">
    <div><b>${tot.length ? fmt(tot.reduce((a, b) => a + b, 0)) : '—'}</b><span>${job.options.mode === 'brand' ? '主页在投广告总数' : '资料库在投总数' + (tot.length > 1 ? '（多个词相加）' : '')}</span></div>
    <div><b>${all.length}</b><span>本次采集（去重后）</span></div>
    ${job.options.mode === 'brand' ? `<div><b>${tot.length && tot[0] ? Math.round(all.length / tot[0] * 100) + '%' : '—'}</b><span>本次覆盖主页在投广告的比例</span></div>`
      : `<div><b>${(ins.advertisers || []).length}</b><span>在投的店铺主页</span></div>`}
    <div><b>${(ins.verdicts || {})['常青爆款'] || 0} / ${(ins.verdicts || {})['新起量'] || 0}</b><span>常青爆款 / 新起量</span></div>
    <div><b>${Math.round(vids / all.length * 100)}%</b><span>视频素材占比</span></div>
    <div><b>${days[Math.floor(days.length / 2)]} 天</b><span>在投天数中位数</span></div>
    <div><b>${ins.video?.medianSeconds ? ins.video.medianSeconds + 's' : '—'}</b><span>视频时长中位数${ins.video?.medianShot ? ` · 平均 ${ins.video.medianShot}s 一个镜头` : ''}</span></div>
    <div><b>${prices.length ? prices[Math.floor(prices.length / 2)] : '—'}</b><span>落地页售价中位数${prices.length ? `（${prices.length} 个商品，${prices[0]}–${prices[prices.length - 1]}；各店默认币种）` : ''}</span></div></div>`;
  const top = `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 10px;font-size:14.5px">爆款指数最高的素材 <span class="muted">（在投天数 + 同素材广告数 + 曝光排序位置 + 平台数，Meta 不公开花费和点赞，这是用公开字段做的近似）</span></h3>
    <div class="tiles">${all.slice(0, 8).map(a => tile(a)).join('')}</div></div>`;
  const charts = `<div class="charts">
    <div class="card"><h3>素材形式</h3>${bars(ins.formats, {label: fmtName})}</div>
    <div class="card"><h3>投放状态判定</h3>${bars(ins.verdicts)}</div>
    <div class="card"><h3>在投天数分布</h3>${bars(ins.daysLive, {keep: true})}</div>
    <div class="card"><h3>近半年每周新上线（本次样本）</h3>${weeks(ins.weekly)}</div>
    <div class="card"><h3>文案里的卖点/促销手法</h3>${bars(ins.tags)}</div>
    <div class="card"><h3>文案开头类型</h3>${bars(ins.hookTypes)}</div>
    <div class="card"><h3>文案长度</h3>${bars(ins.lengths)}</div>
    <div class="card"><h3>CTA 按钮</h3>${bars(ins.ctas)}</div>
    ${ins.video ? `<div class="card"><h3>视频时长（已拆解 ${ins.video.count} 条）</h3>${bars(ins.video.lengths, {keep: true})}<div class="muted" style="margin-top:8px">画幅：${esc(Object.entries(ins.video.aspects || {}).map(([k, v]) => `${k} ×${v}`).join('，'))} · 有口播 ${ins.video.withVoice} 条</div></div>` : ''}
    ${ins.image ? `<div class="card"><h3>图片画幅与色调（${ins.image.count} 张）</h3>${bars(ins.image.aspects)}<div style="margin-top:8px">${bars(ins.image.tones, {n: 5})}</div></div>` : ''}
    <div class="card"><h3>投放平台</h3>${bars(ins.platforms)}</div>
    <div class="card"><h3>高频词组 <span class="muted">（按使用的店铺数）</span></h3><div class="chips">${(ins.phrases || []).slice(0, 24).map(p => `<span>${esc(p.text)}<i>${p.count}</i></span>`).join('') || '<span class="muted">暂无</span>'}</div></div>
  </div>`;
  let ai = `<div class="card empty" style="margin-bottom:14px">还没有 AI 总结。${esc(job.steps?.analysis?.msg || '')}</div>`;
  if (s) {
    ai = `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 6px">竞争格局（AI）</h3><div>${esc(s.overview)}</div>
        ${(s.products || []).length ? `<h3 style="margin:12px 0 6px;font-size:14px">产品与价格带</h3><ul style="margin:0;padding-left:18px">${li(s.products)}</ul>` : ''}</div>
      <div class="summary">
        <div class="card"><h3>关键发现</h3>${(s.signals || []).map(x => `<div class="signal"><b>${esc(x.title)}</b>${esc(x.body)}</div>`).join('')}</div>
        <div style="display:flex;flex-direction:column;gap:14px">
          <div class="card"><h3>给你的素材建议</h3><ul>${li(s.recommendations)}</ul></div>
          <div class="card"><h3>空白机会</h3><ul>${li(s.opportunities)}</ul></div>
          <div class="card"><h3>跑得久的卖点角度</h3><ul>${li(s.winningAngles)}</ul></div>
          <div class="card"><h3>优惠与价格策略</h3><ul>${li(s.offers)}</ul></div>
        </div></div>
      <div class="summary" style="margin-top:14px">
        <div class="card"><h3>开头钩子套路</h3><ul>${li(s.hookPatterns)}</ul></div>
        <div class="card"><h3>视频脚本与剪辑套路</h3><ul>${li(s.videoPatterns)}</ul></div>
        <div class="card"><h3>图片画面套路</h3><ul>${li(s.visualPatterns)}</ul></div>
      </div>
      <h3 style="margin:20px 0 0">可以直接拍的 3 个素材方案</h3>
      <div class="concepts">${(s.concepts || []).map(c => `<div class="card concept"><h4>${esc(c.name)}</h4><div class="muted">${esc(c.format)} · 角度：${esc(c.angle)}</div>
        <div style="margin-top:6px"><b>前 3 秒：</b>${esc(c.hook)}</div><ol>${li(c.outline)}</ol>
        <div class="pt"><b>Headline：</b>${esc(c.headline)}\n\n${esc(c.primaryText)}</div><div class="muted" style="margin-top:6px">参考：${esc(c.reference)}</div></div>`).join('')}</div>`;
  }
  return stat + top + ai + `<h3 style="margin:22px 0 10px">本地统计</h3>` + charts;
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
      <input type="text" id="fQ" placeholder="搜索文案、店铺、落地页、口播…" value="${esc(f.q)}">
      <select id="fFormat"><option value="">全部形式</option><option value="VIDEO">视频</option><option value="IMAGE">图片类</option>
        ${[...new Set(all.map(a => a.format))].filter(Boolean).map(x => `<option value="${esc(x)}">${esc(fmtName(x))}</option>`).join('')}</select>
      <select id="fVerdict"><option value="">全部判定</option>${['常青爆款', '新起量', '稳定在投', '在投', '测试中'].map(v => `<option>${v}</option>`).join('')}</select>
      <select id="fSort"><option value="score">按爆款指数</option><option value="days">按在投天数</option><option value="variants">按同素材广告数</option>
        <option value="imp">按曝光排序位置</option><option value="newest">最新上线在前</option><option value="copy">按 AI 文案分</option></select>
      <label class="noexport"><input type="checkbox" id="fStar" ${f.star ? 'checked' : ''}> 只看收藏</label>
      <span class="muted">${list.length} / ${all.length} 条</span></div>
    ${pageName ? `<div class="aibar" style="margin-bottom:12px">只看店铺：<b>${esc(pageName)}</b><button class="btn sm" id="fClearPage">清除</button></div>` : ''}
    ${list.length ? `<div class="tiles">${list.slice(0, state.limit).map(a => tile(a)).join('')}</div>` : '<div class="card empty">没有符合条件的素材</div>'}
    ${list.length > state.limit ? `<button class="btn more" id="moreBtn">再显示 ${Math.min(60, list.length - state.limit)} 条</button>` : ''}`;
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
  const shots = x.script?.length ? `<div class="tablewrap"><table class="shots"><thead><tr><th>时间</th><th>画面</th><th>口播/声音</th><th>作用</th></tr></thead><tbody>${
    x.script.map(s => `<tr><td>${esc(s.time)}</td><td>${esc(s.visual)}</td><td>${esc(s.audio || '—')}</td><td>${esc(s.purpose)}</td></tr>`).join('')}</tbody></table></div>` : '';
  return `<div class="an">
    <dl class="kv">${x.product ? `<dt>产品</dt><dd>${esc(x.product)}</dd>` : ''}<dt>形式</dt><dd>${esc(x.creativeType)}</dd><dt>卖点角度</dt><dd><b>${esc(x.angle)}</b></dd>
      <dt>钩子</dt><dd>${esc(x.hook)}</dd>${x.structure ? `<dt>结构</dt><dd>${esc(x.structure)}</dd>` : ''}${x.pace ? `<dt>节奏</dt><dd>${esc(x.pace)}</dd>` : ''}
      ${x.visual ? `<dt>画面</dt><dd>${esc(x.visual)}</dd>` : ''}${x.textInImage ? `<dt>图中文字</dt><dd>${esc(x.textInImage)}</dd>` : ''}<dt>目标人群</dt><dd>${esc(x.audience)}</dd></dl>
    ${shots}
    <div class="box pros"><b>优点</b><ul>${li(x.strengths)}</ul></div>
    <div class="box cons"><b>可改良的空间</b><ul>${li(x.improvements)}</ul></div>
    <div class="box bor"><b>我方可以直接借鉴</b>${esc(x.borrow)}</div>
    <div class="box rew"><b>${kind === 'video' ? '改良脚本思路' : '改写后的主文案'}</b>${esc(x.rewrite)}</div></div>`;
}
function copyReviewBlock(c) {
  if (!c) return '';
  return `<dl class="kv"><dt>卖点角度</dt><dd>${esc(c.angle)}</dd><dt>钩子类型</dt><dd>${esc(c.hookType)}</dd><dt>文案结构</dt><dd>${esc(c.formula)}</dd>
    <dt>优惠</dt><dd>${esc(c.offer)}</dd><dt>文案力</dt><dd><b>${c.score}/10</b> · ${esc(c.note)}</dd></dl>`;
}
function renderVideos() {
  const vs = ads().filter(a => a.video);
  const rest = ads().filter(a => a.videos?.length && !a.video).length;
  if (!vs.length) return '<div class="card empty">还没有拆解过的视频（在“素材数量”里调大“拆解视频”，或在素材详情里点“AI 拆解”）</div>';
  return `<div class="muted" style="margin-bottom:10px">已下载并拆解 ${vs.length} 条视频（按爆款指数）${rest ? `；另有 ${rest} 条视频未下载，可在素材库里打开详情单独拆解` : ''}。</div>
    <div class="vlist">${vs.map(a => {
    const v = a.video;
    return `<div class="card vcard"><div>
        ${a.localVideo ? `<video controls preload="none" style="width:100%;border-radius:12px;background:#000" poster="${asset(a.thumb)}" src="${asset(a.localVideo)}"></video>` : ''}
        <div class="nums muted" style="margin-top:6px">${v.seconds}s · ${esc(v.aspect || '')} · ${v.shots} 个镜头 · ${esc(v.pace || '')}</div></div>
      <div style="display:flex;flex-direction:column;gap:8px;min-width:0">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b class="linkbtn" data-ad="${esc(a.id)}" role="button" tabindex="0">#${a.rank} ${esc(a.pageName)} · 爆款指数 ${a.score} · ${esc(a.verdict)}</b>
          <span class="muted">在投 ${a.daysLive} 天${a.variants > 1 ? ` · ${a.variants} 条同素材` : ''}</span></div>
        ${v.hookFrames ? `<div><div class="muted">前 3 秒钩子帧</div><img class="sheet" src="${asset(v.hookFrames)}" alt="前 3 秒画面" loading="lazy"></div>` : ''}
        ${v.transcript?.text ? `<div class="copy" style="max-height:110px;overflow:auto"><b>口播：</b>${esc(v.transcript.text)}</div>` : '<div class="muted">无口播（或只有背景音乐）</div>'}
        ${a.analysis ? `<details><summary style="cursor:pointer;color:var(--blue);font-weight:700">AI 拆解：${esc(a.analysis.creativeType)} · ${esc(a.analysis.structure || '')}</summary>${analysisBlock(a.analysis, 'video')}</details>`
          : `<button class="btn sm noexport" data-aiad="${esc(a.id)}" style="align-self:flex-start">${a.aiStatus === 'running' || a.aiStatus === 'queued' ? esc(a.aiMsg) : 'AI 拆解这条'}</button>`}
      </div></div>`;
  }).join('')}</div>`;
}
function renderImages() {
  const xs = ads().filter(a => !a.videos?.length && a.imageInfo);
  if (!xs.length) return '<div class="card empty">没有图片素材</div>';
  return `<div class="tiles" style="grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr))">${xs.map(a => `<div class="card" style="padding:0;overflow:hidden">
      ${tile(a).replace('class="tile"', 'class="tile" style="border:0;box-shadow:none;border-radius:0"')}
      <div style="padding:0 12px 12px;display:flex;flex-direction:column;gap:6px">
        <div class="sw">${(a.imageInfo.colors || []).map(c => `<i style="background:${esc(c.hex)}" title="${esc(c.hex)} ${c.pct}%"></i>`).join('')}<span class="muted" style="margin-left:6px">${esc(a.imageInfo.aspect || '')} · ${esc(a.imageInfo.tone || '')}</span></div>
        ${a.analysis ? `<div style="font-size:13px"><b>${esc(a.analysis.creativeType)}</b> · ${esc(a.analysis.angle)}</div><div class="muted">${esc(a.analysis.hook)}</div>` : ''}
        ${a.analysis?.textInImage ? `<div class="muted"><b>图中文字：</b>${esc(a.analysis.textInImage)}</div>` : ''}</div></div>`).join('')}</div>`;
}
function renderCopy() {
  const list = ads().filter(a => a.body || a.title);
  const sorted = [...list].sort((a, b) => state.copySort === 'ai' ? (b.copyReview?.score || 0) - (a.copyReview?.score || 0) : a.rank - b.rank);
  const reviewed = list.filter(a => a.copyReview).length;
  return `<div class="viewbar" style="display:flex;gap:6px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <button class="tab ${state.copySort !== 'ai' ? 'on' : ''}" data-csort="rank">按爆款指数</button><button class="tab ${state.copySort === 'ai' ? 'on' : ''}" data-csort="ai">按 AI 文案分</button>
      <span class="muted">${list.length} 条有文案 · AI 点评 ${reviewed} 条</span></div>
    <div class="card pad tablewrap"><table class="list"><thead><tr><th>#</th><th>店铺</th><th>主文案</th><th>标题 / CTA</th><th>本地标签</th><th>AI 角度 · 结构</th><th>AI 分</th><th>在投</th></tr></thead><tbody>${
    sorted.map(a => `<tr><td class="num"><button class="linkbtn" data-ad="${esc(a.id)}">${a.rank}</button></td><td>${esc(a.pageName)}</td>
      <td><div class="clip">${esc(a.body)}</div></td><td>${esc(a.title || '')}<div class="muted">${esc(a.cta || '')}${a.linkDescription ? ' · ' + esc(a.linkDescription) : ''}</div></td>
      <td><div class="tags">${(a.copy?.tags || []).map(t => `<span>${esc(t)}</span>`).join('')}</div><div class="muted">${esc(a.copy?.hookType || '')} · ${a.copy?.chars || 0} 字符${a.copy?.emojis ? ` · ${a.copy.emojis} 表情` : ''}</div></td>
      <td>${a.copyReview ? `<b>${esc(a.copyReview.angle)}</b><div class="muted">${esc(a.copyReview.hookType)} · ${esc(a.copyReview.formula)}</div><div style="font-size:12.5px">${esc(a.copyReview.note)}</div>` : '<span class="muted">—</span>'}</td>
      <td class="num">${a.copyReview ? `<b>${a.copyReview.score}</b>` : '—'}</td><td class="num">${a.daysLive} 天</td></tr>`).join('')}</tbody></table></div>`;
}

/* ---------------- 店铺 / 商品 ---------------- */
function renderShops() {
  const xs = state.job.results?.insights?.advertisers || [];
  if (!xs.length) return '<div class="card empty">暂无</div>';
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">点店铺名可以在素材库里只看这家店。“同素材”= 资料库里“N 条广告使用了这个素材和文案”的合计，越多说明在加预算铺量。</div>
    <table class="list"><thead><tr><th>店铺主页</th><th>粉丝</th><th>素材数</th><th>视频/图片</th><th>最长在投</th><th>中位在投</th><th>同素材合计</th><th>近 14 天新上</th><th>最高爆款指数</th><th>落地域名</th></tr></thead><tbody>${
    xs.map(p => `<tr><td><div style="display:flex;gap:8px;align-items:center">${p.avatar ? `<img class="av" style="width:28px;height:28px" src="${asset(p.avatar)}" alt="">` : ''}
        <div><button class="linkbtn" data-page="${esc(p.pageId)}">${esc(p.pageName)}</button>${p.pageUrl ? ` <a class="muted" href="${esc(p.pageUrl)}" target="_blank" rel="noopener">主页↗</a>` : ''}
        <div class="muted">${esc((p.categories || []).join('、'))}</div></div></div></td>
      <td class="num">${fmt(p.likes)}</td><td class="num">${p.ads}</td><td class="num">${p.videos} / ${p.images}</td><td class="num">${p.maxDays} 天</td><td class="num">${p.medianDays} 天</td>
      <td class="num">${p.variants}</td><td class="num">${p.newLast14}</td><td class="num"><b>${p.bestScore}</b></td>
      <td>${(p.domains || []).map(d => esc(d)).join('<br>')}${p.shopify ? ' <span class="chip done">Shopify</span>' : ''}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderProducts() {
  const ins = state.job.results?.insights || {};
  const ps = ins.products || [];
  const disc = p => p.compareAt && p.price && p.compareAt > p.price ? `-${Math.round((1 - p.price / p.compareAt) * 100)}%` : '';
  const same = (ins.sameProduct || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">同款竞争：同一个商品被多家店推</h3><table class="list"><thead><tr><th>商品</th><th>店铺</th><th>广告数</th><th>售价</th></tr></thead><tbody>${
    ins.sameProduct.map(g => `<tr><td><b>${esc(g.name)}</b></td><td>${g.shops.map(esc).join('<br>')}</td><td class="num">${g.ads}</td><td class="num">${g.prices.length ? g.prices.map(p => '$' + p).join(' / ') : '—'}</td></tr>`).join('')}</tbody></table></div>` : '';
  const sameCopy = (ins.sameCopy || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">同一段文案被多个主页使用（铺货 / 同源素材）</h3><table class="list"><tbody>${
    ins.sameCopy.slice(0, 15).map(g => `<tr><td><div class="clip">${esc(g.snippet)}…</div></td><td>${g.pages.map(esc).join('<br>')}</td><td><button class="linkbtn" data-ad="${esc(g.adIds[0])}">看素材</button></td></tr>`).join('')}</tbody></table></div>` : '';
  const sameCr = (ins.sameCreative || []).length ? `<div class="card pad" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">同一张图/同一条视频被多个主页使用</h3><div class="tiles">${
    ins.sameCreative.slice(0, 12).map(g => `<div class="card" style="padding:8px"><img class="sheet" src="${asset(g.thumb)}" alt="" loading="lazy"><div class="muted" style="margin-top:6px">${g.pages.map(esc).join('、')}</div><button class="linkbtn" data-ad="${esc(g.adIds[0])}">看素材</button></div>`).join('')}</div></div>` : '';
  return same + `<div class="card pad tablewrap" style="margin-bottom:14px"><h3 style="margin:0 0 8px;font-size:14.5px">落地商品（${ps.length}）</h3>
    <div class="muted" style="margin-bottom:8px">广告落地到 Shopify 商品页时，读取了公开的商品名、售价、原价和上架日期。价格是店铺默认币种。</div>
    <table class="list"><thead><tr><th></th><th>商品</th><th>店铺</th><th>售价</th><th>原价</th><th>折扣</th><th>上架</th><th>广告数</th><th>推广主页</th><th>最长在投</th><th>素材</th></tr></thead><tbody>${
    ps.map(p => `<tr><td>${p.image ? `<img class="pimg" src="${esc(p.image)}" alt="" loading="lazy">` : ''}</td><td><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>${p.variants ? `<div class="muted">${p.variants} 个规格</div>` : ''}</td>
      <td>${esc(p.domain)}</td><td class="num">${p.price ? '$' + p.price : '—'}</td><td class="num">${p.compareAt ? '$' + p.compareAt : '—'}</td><td class="num">${disc(p)}</td>
      <td class="num">${esc(p.createdAt || '—')}</td><td class="num">${p.ads}</td><td>${p.pages.map(esc).join('<br>')}</td><td class="num">${p.maxDays} 天</td>
      <td><button class="linkbtn" data-ad="${esc(p.adIds[0])}">看素材</button></td></tr>`).join('')}</tbody></table></div>` + sameCopy + sameCr;
}
function renderQueries() {
  const qs = state.job.results?.queries || [];
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">未登录时 Meta 每次只返回 30 条，所以用多组排序/筛选组合分别查询，再合并去重。点链接可以在浏览器里打开同样的资料库页面。</div>
    <table class="list"><thead><tr><th>关键词</th><th>查询</th><th>资料库总数</th><th>拿到</th><th>新增</th><th>链接</th></tr></thead><tbody>${
    qs.map(q => `<tr><td>${esc(q.keyword)}</td><td>${esc(q.label)}</td><td class="num">${fmt(q.total)}</td><td class="num">${q.got}</td><td class="num">${q.new}</td>
      <td><a href="${esc(q.url)}" target="_blank" rel="noopener">打开↗</a>${q.error ? `<div class="err">${esc(q.error)}</div>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
}

function brandCard(job) {
  const b = job.results?.brand;
  if (job.options.mode !== 'brand') return '';
  if (!b?.page) return `<div class="brandcard"><span>🏷 品牌模式：正在识别“${esc(job.keyword)}”的官方主页…</span></div>`;
  const p = b.page;
  const av = ads().find(a => a.pageId === p.pageId)?.localAvatar;
  return `<div class="brandcard">${av ? `<img src="${asset(av)}" alt="">` : ''}
    <div style="flex:1;min-width:200px"><div class="muted">🏷 品牌模式 · 官方主页</div><b>${esc(p.pageName || p.pageId)}</b>
      ${p.pageUrl ? ` <a href="${esc(p.pageUrl)}" target="_blank" rel="noopener">主页↗</a>` : ''}
      <div class="muted">${p.likes ? fmt(p.likes) + ' 粉丝 · ' : ''}主页在投 ${fmt(p.pageTotal)} 条 · 本次拿到 ${ads().length} 条${p.reasons?.length ? ' · 识别依据：' + esc(p.reasons.join('、')) : ''}</div></div>
    ${b.candidates?.length > 1 ? `<button class="btn sm" data-tab-go="brand">不是这个主页？</button>` : ''}</div>`;
}
function renderBrand() {
  const b = state.job.results?.brand;
  if (!b?.candidates?.length) return '<div class="card empty">没有其他候选主页（主页是直接指定的）</div>';
  return `<div class="card pad tablewrap"><div class="muted" style="margin-bottom:8px">按“${esc(b.input)}”搜索资料库时出现的广告主页，按匹配得分排序。选错了就点“改抓这个主页”，会用同样的设置新建一个任务。</div>
    <table class="list"><thead><tr><th>主页</th><th>得分</th><th>识别依据</th><th>粉丝</th><th>落地域名</th><th></th></tr></thead><tbody>${
    b.candidates.map(c => `<tr><td><b>${esc(c.pageName)}</b>${c.pageUrl ? ` <a class="muted" href="${esc(c.pageUrl)}" target="_blank" rel="noopener">主页↗</a>` : ''}<div class="muted">ID ${esc(c.pageId)}</div></td>
      <td class="num"><b>${c.score}</b></td><td>${esc((c.reasons || []).join('、') || '—')}</td><td class="num">${fmt(c.likes)}</td>
      <td>${esc(Object.keys(c.domains || {}).join('、'))}</td>
      <td>${c.pageId === b.page.pageId ? '<span class="chip done">当前</span>' : `<button class="btn sm noexport" data-repage="${esc(c.pageId)}">改抓这个主页</button>`}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderJob(focus) {
  const job = state.job, r = job.results || {}, steps = job.steps || {};
  const running = ['queued', 'running'].includes(job.status);
  const all = ads();
  const tabs = [['summary', '总结'], ['library', `素材库 (${all.length})`], ['videos', `视频拆解 (${all.filter(a => a.video).length})`],
    ['images', `图片 (${all.filter(a => !a.videos?.length && a.imageInfo).length})`], ['copy', `文案 (${all.filter(a => a.body || a.title).length})`],
    ['shops', `店铺 (${(r.insights?.advertisers || []).length})`], ['products', `商品与同款 (${(r.insights?.products || []).length})`], ['queries', '查询记录']];
  if (job.options.mode === 'brand') tabs.splice(1, 0, ['brand', '品牌主页']);
  if (!STATIC) tabs.push(['log', '运行日志']);
  const body = {brand: renderBrand, library: renderLibrary, videos: renderVideos, images: renderImages, copy: renderCopy, shops: renderShops, products: renderProducts, queries: renderQueries,
    log: () => `<div class="log">${esc((job.log || []).join('\n'))}</div>`}[state.tab] || (() => renderSummary(job));
  const notices = job.notices || [];
  $('#main').innerHTML = `<div class="card head">
      <div style="min-width:0"><h1>${esc(job.keyword)}</h1>
        <div class="meta">${esc(job.createdAt.replace('T', ' '))} · ${esc(state.settings?.countries?.[job.options.country] || job.options.country)} · ${esc({quick: '快速', standard: '标准', deep: '深度'}[job.options.depth] || '')}采集 ·
          <span class="chip ${job.status}">${STATUS_CN[job.status] || job.status}</span>${running && job.current ? ' · ' + esc(job.current) : ''}${job.usage ? ` · AI 调用 ${job.usage.calls} 次` : ''}</div></div>
      <div class="btns">
        ${running ? '<button class="btn danger" data-act="cancel">取消</button>' : '<button class="btn primary" data-act="analyze">AI 分析</button><button class="btn" data-act="rerun">重新抓取</button>'}
        <button class="btn" data-act="export" ${running ? 'disabled' : ''}>导出报告</button><button class="btn" data-act="csv" ${running ? 'disabled' : ''}>导出 CSV</button>
        <button class="btn" data-act="open">打开文件夹</button>${running ? '' : '<button class="btn danger" data-act="delete">删除</button>'}</div>
      <div class="steps">${Object.entries(steps).map(([k, s]) => `<div class="step ${s.status}"><b><span class="ico">${STEP_ICON[s.status] || ''}</span>${esc(s.label)}</b><div class="msg">${esc(s.msg || '')}</div></div>`).join('')}</div>
      ${brandCard(job)}
      ${notices.length ? `<div class="notices"><b>提示和抓不到的内容</b><ul>${notices.map(n => `<li class="${n.level}"><b style="color:inherit">${esc(n.scope)}：</b>${esc(n.message)}</li>`).join('')}</ul></div>` : ''}
    </div>
    <div class="tabs">${tabs.map(([k, t]) => `<button class="tab ${state.tab === k ? 'on' : ''}" data-tab="${k}">${esc(t)}</button>`).join('')}</div>
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
  if (s.engine === 'none') { alert('设置里的分析引擎是“不做 AI 分析”，请先选择 Claude Code 或 Claude API'); openSettings(); return; }
  if (s.engine === 'api' && !s.has_api_key) { alert('分析引擎是 Claude API，请先填写 API key'); openSettings(); return; }
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
    : a.thumb ? `<img class="sheet" src="${asset(a.thumb)}" alt="">${a.videos?.length ? '<div class="muted" style="margin-top:6px">视频还没有下载。点“AI 拆解这条”会先下载、做分镜和转写。</div>' : ''}` : '<div class="muted">没有素材画面</div>';
  const cards = a.cards?.length > 1 ? `<div class="card"><h4>轮播/动态素材卡片（${a.cards.length}）</h4>${a.cards.map((x, i) => `<div style="margin-bottom:6px;font-size:13px"><b>${i + 1}. ${esc(x.title || '')}</b> <span class="muted">${esc(x.cta || '')}</span>${x.body && x.body !== a.body ? `<div class="muted">${esc(x.body.slice(0, 200))}</div>` : ''}</div>`).join('')}</div>` : '';
  const aiStatus = ['queued', 'running'].includes(a.aiStatus) ? `<div class="aibar">◐ ${esc(a.aiMsg)}</div>` : a.aiStatus === 'failed' ? `<div class="aibar" style="background:var(--coral-soft)">✕ ${esc(a.aiMsg)}</div>` : '';
  $('#drawerPanel').innerHTML = `<div class="dhead"><b>#${a.rank} ${esc(a.pageName)} · ${esc(fmtName(a.format))}</b>
      <div style="display:flex;gap:6px;flex:none">${STATIC ? '' : `<button class="btn sm" id="dStar">${a.starred ? '★ 已收藏' : '☆ 收藏'}</button>`}
        <a class="btn sm" style="text-decoration:none" href="${esc(a.libraryUrl)}" target="_blank" rel="noopener">资料库↗</a><button class="btn sm" id="dClose">关闭 ✕</button></div></div>
    <div class="dbody"><div>
      <div class="card">${media}</div>
      ${v ? `<div class="card"><h4>视频数据</h4><dl class="kv"><dt>时长</dt><dd>${v.seconds} 秒 · ${esc(v.aspect || '')}</dd><dt>镜头</dt><dd>${v.shots} 个，平均 ${v.avgShot}s 一个 · ${esc(v.pace || '')}</dd>
          <dt>切镜点</dt><dd>${(v.cuts || []).map(t => `<button class="linkbtn" data-seek="${t}">${t}s</button>`).join(' ') || '一镜到底'}</dd><dt>声音</dt><dd>${v.hasAudio ? '有音轨' : '无音轨'}${v.transcript?.lang ? ` · 语言 ${esc(v.transcript.lang)}` : ''}</dd></dl>
        ${v.transcript?.segments?.length ? `<h4 style="margin-top:10px">口播转写（点一行跳到那一秒）</h4><div class="trs">${v.transcript.segments.map(s => `<button data-seek="${s.t}"><i>${s.t}s</i>${esc(s.text)}</button>`).join('')}</div>`
          : v.transcript?.error ? `<div class="err">${esc(v.transcript.error)}</div>` : ''}</div>` : ''}
      ${ii ? `<div class="card"><h4>画面数据</h4><div class="sw">${(ii.colors || []).map(x => `<i style="background:${esc(x.hex)}" title="${esc(x.hex)} ${x.pct}%"></i>`).join('')}</div>
          <div class="muted" style="margin-top:6px">${ii.w}×${ii.h} · ${esc(ii.aspect || '')} · ${esc(ii.tone || '')}</div></div>` : ''}
      <div class="card"><h4>投放数据</h4><dl class="kv"><dt>爆款指数</dt><dd><b>${a.score}</b> · ${esc(a.verdict)}</dd><dt>上线</dt><dd>${esc(a.startDate)}（在投 ${a.daysLive} 天）</dd>
        <dt>同素材广告</dt><dd>${a.variants} 条</dd><dt>曝光排序</dt><dd>${a.impRank ? '第 ' + a.impRank : (a.impRankOther ? '分类列表第 ' + a.impRankOther : '不在前 30')}</dd>
        <dt>平台</dt><dd>${esc((a.platforms || []).join('、'))}</dd><dt>命中查询</dt><dd>${esc((a.hits || []).join('；'))}</dd>
        <dt>主页</dt><dd>${a.pageUrl ? `<a href="${esc(a.pageUrl)}" target="_blank" rel="noopener">${esc(a.pageName)}</a>` : esc(a.pageName)}${a.pageLikes ? ` · ${fmt(a.pageLikes)} 粉丝` : ''}</dd>
        ${a.creatorPage ? `<dt>达人合作</dt><dd>${esc(a.creatorPage)}</dd>` : ''}</dl></div>
    </div><div>
      ${aiStatus}
      <div class="card"><h4>文案</h4><div class="copy">${esc(a.body || '（无主文案）')}</div>
        <dl class="kv" style="margin-top:10px"><dt>标题</dt><dd>${esc(a.title || '—')}</dd><dt>链接描述</dt><dd>${esc(a.linkDescription || '—')}</dd><dt>CTA</dt><dd>${esc(a.cta || '—')}</dd>
          <dt>落地页</dt><dd>${a.linkUrl ? `<a href="${esc(a.linkUrl)}" target="_blank" rel="noopener">${esc(a.linkUrl)}</a>` : '—'}${a.shopPlatform ? ' <span class="chip done">Shopify</span>' : ''}</dd>
          ${p ? `<dt>落地商品</dt><dd><b>${esc(p.title)}</b> · $${p.price}${p.compareAt ? ` <s class="muted">$${p.compareAt}</s>` : ''}${p.createdAt ? ` · 上架 ${esc(p.createdAt)}` : ''}</dd>` : ''}
          <dt>本地标签</dt><dd><div class="tags">${(c.tags || []).map(t => `<span>${esc(t)}</span>`).join('') || '—'}</div></dd>
          <dt>开头</dt><dd>${esc(c.hookType || '')} · ${c.chars || 0} 字符 · ${c.lines || 0} 行${c.emojis ? ` · ${c.emojis} 个表情` : ''}${c.maxPctOff ? ` · 最高 ${c.maxPctOff}% off` : ''}</dd></dl>
        ${a.copyReview ? `<h4 style="margin-top:12px">AI 文案点评</h4>${copyReviewBlock(a.copyReview)}` : ''}</div>
      ${cards}
      ${v?.hookFrames ? `<div class="card"><h4>前 3 秒钩子帧</h4><img class="sheet" src="${asset(v.hookFrames)}" alt=""></div>` : ''}
      ${v?.storyboard ? `<div class="card"><h4>逐秒分镜（含切镜点）</h4><a href="${asset(v.storyboard)}" target="_blank" rel="noopener"><img class="sheet" src="${asset(v.storyboard)}" alt=""></a></div>` : ''}
      <div class="card"><h4>AI 拆解</h4>${a.analysis ? analysisBlock(a.analysis, a.analysis.kind) : `<div class="muted" style="margin-bottom:8px">还没有 AI 拆解。</div>`}
        ${STATIC ? '' : `<button class="btn primary sm" style="margin-top:10px" id="dAi" ${['queued', 'running'].includes(a.aiStatus) || ['queued', 'running'].includes(state.job.status) ? 'disabled' : ''}>${a.analysis ? '重新 AI 拆解' : 'AI 拆解这条'}</button>`}</div>
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
  if (act === 'delete' && !confirm('删除这个任务和它下载的所有素材？收藏的素材也会一起删除。')) return;
  if (act === 'analyze') {
    const s = state.settings || {};
    if (s.engine === 'none') { alert('设置里的分析引擎是“不做 AI 分析”，请先选择 Claude Code 或 Claude API'); openSettings(); return; }
    if (s.engine === 'api' && !s.has_api_key) { alert('分析引擎是 Claude API，请先填写 API key；或者改用 Claude Code（用订阅，不需要 key）'); openSettings(); return; }
  }
  try {
    const r = await api(`/api/jobs/${encodeURIComponent(id)}/${act}`, {method: 'POST'});
    if (act === 'delete') { state.cur = null; state.job = null; closeDrawer(); await loadJobs(); welcome(); return; }
    if (act === 'rerun') { state.tab = 'summary'; await loadJobs(); openJob(r.id); return; }
    if (act === 'export') alert('已导出：' + r.path + '\n把整个任务文件夹打包，就能发给别人用浏览器打开（视频和图片都在 assets 文件夹里）。');
    if (act === 'csv') { alert('已导出：' + r.path + '\n可以直接用 Excel 打开。'); return; }
    state.sig = ''; openJob(id);
  } catch (e) { alert(e.message); }
}

/* ---------------- 收藏夹 ---------------- */
async function showStarred() {
  clearTimeout(state.timer);
  state.cur = null; loadJobs();
  try { state.starred = await api('/api/starred'); } catch (e) { $('#main').innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; }
  const xs = state.starred;
  $('#main').innerHTML = `<div class="card head"><div><h1>★ 收藏夹</h1><div class="meta">所有任务里收藏的素材，共 ${xs.length} 条。点素材打开它所在的任务和详情。</div></div></div>
    <div style="margin-top:14px">${xs.length ? `<div class="tiles">${xs.map(a => tile(a, a.jobId).replace('<div class="tb">', `<div class="tb"><span class="muted">${esc(a.jobKeyword)}</span>`)).join('')}</div>`
      : '<div class="card empty">还没有收藏。在素材上点 ☆ 就能收藏。</div>'}</div>`;
  bindCommon($('#main'));
}
$('#btnStarred').onclick = showStarred;

/* ---------------- 欢迎页 / 环境检查 / 设置 ---------------- */
async function welcome() {
  $('#main').innerHTML = `<div class="card welcome"><h2>使用步骤</h2><ol>
    <li>打开代理/VPN（要能访问 facebook.com）。Meta 广告资料库按你选的<b>投放国家</b>筛选，不需要把节点切到那个国家。</li>
    <li>点右上角“设置”，选择 AI 分析引擎：<b>Claude Code</b>（用你的 Claude 订阅，需先在终端运行 <code>claude</code> 并 <code>/login</code>）或 <b>Claude API</b>（填 API key）。不分析也能抓取，本地统计照样有。</li>
    <li>在左侧输入<b>英文产品词</b>（例如 posture corrector、pet hair remover），多个词用逗号分隔，点“开始抓取”。标准深度一个词大约 3–8 分钟，AI 分析另外 5–15 分钟。</li>
    <li>看“总结”里的爆款素材和 AI 方案；在“素材库”里筛选、打开详情看视频分镜和口播；点 ☆ 收藏好素材，收藏夹跨任务汇总。</li></ol>
    <h2 style="margin-top:22px">环境检查</h2><div id="checkBox" class="muted">检查中…</div></div>`;
  runCheck();
}
async function runCheck() {
  try {
    const rows = await api('/api/check?refresh=1');
    const box = $('#checkBox');
    if (box) box.outerHTML = `<div class="check">${rows.map(r => `<span class="${r.ok ? 'ok' : 'no'}">${r.ok ? '✓' : '✕'} ${esc(r.name)}</span><span>${esc(r.detail)}</span>`).join('')}</div>`;
  } catch (e) { const box = $('#checkBox'); if (box) box.textContent = '检查失败：' + e.message; }
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
if (STATIC) {
  document.body.classList.add('static');
  state.job = STATIC;
  state.settings = {countries: {}};
  document.title = STATIC.keyword + ' · Meta 素材侦察报告';
  renderJob();
} else {
  loadSettings().then(loadJobs).then(() => state.jobs[0] ? openJob(state.jobs[0].id) : welcome());
}
