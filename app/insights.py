"""不需要 AI 的本地分析：文案特征与标签、爆款指数、店铺/商品排行、同款竞争、高频词、上线时间分布。"""
import collections
import datetime
import math
import re
import statistics

# 文案标签：(名称, 正则)。面向英文广告，同时兼容常见的西语/德语/法语写法
TAGS = [
    ('折扣', r'\d{1,2}\s?%\s?(off|rabatt|de descuento|de réduction)|\bsave \$?\d+|\bsale\b|\bdiscount|\bdeals?\b|\bcoupon|\bcode\b'),
    ('买赠/赠品', r'\bbuy \d+,? get \d+|\bbogo\b|free gift|\bgift with|\bbonus\b|\b2 for\b|\bbundle'),
    ('包邮', r'free (shipping|delivery)|ships free|envío gratis|kostenloser versand|livraison gratuite'),
    ('限时/稀缺', r'limited (time|stock|edition)|today only|ends (soon|tonight|today)|last chance|\bhurry\b|selling fast|while (supplies|stocks?) last|only \d+ left|\bsold out\b|restock'),
    ('社会证明', r'\d[\d,.]*\s?k?\+?\s?(happy )?(customers|reviews|people|sold|buyers|users|orders|moms|women|men)|★|⭐|\brated\b|5[- ]star|trustpilot|best ?sell|\bviral\b|made me buy|\bas seen on\b'),
    ('无风险保障', r'money[- ]back|\bguarantee|risk[- ]free|\d+[- ]days? (return|trial|refund)|\bwarranty|free returns'),
    ('痛点', r'tired of|struggl|suffer|\bpain|\bhate\b|sick of|no more|\bfinally\b|\bfix\b|\bstop\b|\bwithout\b|say goodbye'),
    ('专业背书', r'\bdoctor|dermatologist|chiropractor|physio|clinically|\bexperts?\b|scientist|approved|certified|\bpatent|\bfda\b|\blab[- ]tested'),
    ('前后对比', r'\bbefore\b|\bafter\b|\bvs\.?\b|compared to|unlike other|results in \d+'),
    ('节日/送礼', r'\bgifts?\b|christmas|xmas|halloween|black friday|cyber monday|mother.?s day|father.?s day|valentine|holiday|thanksgiving|prime day'),
    ('价格锚点', r'[$€£]\s?\d+|\d+\s?(usd|eur|gbp)\b|only \$|just \$|under \$|less than \$'),
]
TAG_RE = [(n, re.compile(p, re.I)) for n, p in TAGS]
EMOJI_RE = re.compile('[\U0001F300-\U0001FAFF☀-➿⭐✅❌‼⁉]')
STOP = set('''a an the and or but if of to in on for with at by from as is are was were be been it its this that these those you your yours we our us i me my
they them their he she his her not no so do does did can will just get got have has had more most very than then there here what when where which who why how
all any each few other some such only own same too s t don now off up out over into about again once also new one two our now it's you're i'm don't can't
https www com shop now link bio click today order'''.split())


def copy_features(text):
    t = text or ''
    first = next((ln.strip() for ln in t.splitlines() if ln.strip()), '')
    tags = [n for n, rx in TAG_RE if rx.search(t)]
    pct = [int(x) for x in re.findall(r'(\d{1,2})\s?%', t)]
    prices = re.findall(r'[$€£]\s?\d+(?:[.,]\d{2})?', t)
    if first.endswith('?'):
        hook = '提问'
    elif re.match(r'^\W*\d', first):
        hook = '数字开头'
    elif EMOJI_RE.match(first):
        hook = '表情开头'
    elif re.search(r'(?i)tired of|struggl|suffer|pain|hate|sick of|no more|stop', first):
        hook = '痛点开头'
    elif first.isupper() and len(first) > 6:
        hook = '全大写'
    elif first.endswith('!'):
        hook = '感叹句'
    else:
        hook = '陈述句'
    return {'chars': len(t), 'words': len(re.findall(r'\w+', t)), 'lines': len([x for x in t.splitlines() if x.strip()]),
            'emojis': len(EMOJI_RE.findall(t)), 'hashtags': re.findall(r'#\w+', t)[:10], 'firstLine': first[:200],
            'hookType': hook, 'tags': tags, 'maxPctOff': max(pct) if pct else None, 'prices': prices[:5],
            'length': '短（≤125 字符）' if len(t) <= 125 else ('中（126–400）' if len(t) <= 400 else '长（>400）')}


def score(a, run_date):
    """爆款指数 0–100：在投天数（35）+ 同素材广告数（20）+ 曝光排序位置（30）+ 投放平台数（5）+ 新起量加分（10）。
    Meta 不公开点赞、花费和美国曝光，这是用资料库公开字段做的近似。"""
    days = (run_date - datetime.date.fromisoformat(a['startDate'])).days if a.get('startDate') else 0
    a['daysLive'] = days
    s = min(days, 90) / 90 * 35
    s += min(math.log2((a.get('variants') or 1)) / 3, 1) * 20
    if a.get('impRank'):
        s += (31 - min(a['impRank'], 30)) / 30 * 30
    elif a.get('impRankOther'):
        s += (31 - min(a['impRankOther'], 30)) / 30 * 18
    s += min(len(a.get('platforms') or []), 4) / 4 * 5
    rising = days <= 21 and (a.get('impRank') or a.get('impRankOther') or 99) <= 30
    if rising:
        s += 10
    a['score'] = round(min(s, 100))
    imp, var = a.get('impRank') or 99, a.get('variants') or 1
    if days >= 60 and (imp <= 10 or (imp <= 30 and var >= 2) or var >= 4):
        a['verdict'] = '常青爆款'
    elif rising:
        a['verdict'] = '新起量'
    elif days <= 7:
        a['verdict'] = '测试中'
    elif days >= 30:
        a['verdict'] = '稳定在投'
    else:
        a['verdict'] = '在投'
    return a['score']


def _phrases(ads, n_top=30):
    """高频词组：按“有多少个不同主页在用”计数，避免一家店铺几十条同文案刷屏。"""
    per_page = collections.defaultdict(set)
    for a in ads:
        per_page[a.get('pageId') or a.get('pageName')].update(_grams(' '.join(x for x in (a.get('body'), a.get('title')) if x)))
    cnt = collections.Counter(g for gs in per_page.values() for g in gs)
    return [{'text': k, 'count': v} for k, v in cnt.most_common(n_top) if v >= 2]


def _grams(t):
    words = re.findall(r"[a-zA-Z][a-zA-Z'’-]+", (t or '').lower())
    seen = set()
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            g = words[i:i + n]
            if g[0] in STOP or g[-1] in STOP or sum(w in STOP for w in g) > n - 2 + (n == 3):
                continue
            seen.add(' '.join(g))
    return seen


def _norm_body(t):
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:400]


def aggregate(ads, run_date):
    for a in ads:
        a['copy'] = copy_features('\n'.join(x for x in (a.get('body'), a.get('title'), a.get('linkDescription')) if x))
        score(a, run_date)
    ads.sort(key=lambda a: (-a['score'], a.get('impRank') or 99))
    for i, a in enumerate(ads, 1):
        a['rank'] = i
    C = collections.Counter
    out = {
        'total': len(ads),
        'formats': dict(C(a.get('format') or '其他' for a in ads)),
        'verdicts': dict(C(a['verdict'] for a in ads)),
        'ctas': dict(C(a.get('cta') or '无' for a in ads).most_common(10)),
        'platforms': dict(C(p for a in ads for p in a.get('platforms') or [])),
        'tags': dict(C(t for a in ads for t in a['copy']['tags']).most_common()),
        'hookTypes': dict(C(a['copy']['hookType'] for a in ads if a.get('body'))),
        'lengths': dict(C(a['copy']['length'] for a in ads if a.get('body'))),
        'phrases': _phrases(ads),
        'emojiAds': sum(1 for a in ads if a['copy']['emojis']),
    }
    buckets = [('≤7 天', -1, 7), ('8–30 天', 7, 30), ('31–90 天', 30, 90), ('91–180 天', 90, 180), ('180 天以上', 180, 10 ** 6)]
    out['daysLive'] = {lab: sum(1 for a in ads if lo < a['daysLive'] <= hi) for lab, lo, hi in buckets}
    # 近 26 周每周新上线数（只统计本次抓到的样本）
    weeks = C()
    for a in ads:
        if a.get('startDate'):
            d = datetime.date.fromisoformat(a['startDate'])
            if (run_date - d).days <= 182:
                weeks[str(d - datetime.timedelta(days=d.weekday()))] += 1
    out['weekly'] = dict(sorted(weeks.items()))

    # 店铺（广告主主页）排行
    pages = collections.defaultdict(list)
    for a in ads:
        pages[a.get('pageId') or a.get('pageName')].append(a)
    out['advertisers'] = sorted([{
        'pageId': k, 'pageName': xs[0].get('pageName'), 'pageUrl': xs[0].get('pageUrl'), 'avatar': xs[0].get('localAvatar'),
        'likes': xs[0].get('pageLikes'), 'categories': xs[0].get('pageCategories'), 'ads': len(xs),
        'videos': sum(1 for a in xs if a.get('videos')), 'images': sum(1 for a in xs if not a.get('videos')),
        'maxDays': max(a['daysLive'] for a in xs), 'medianDays': round(statistics.median(a['daysLive'] for a in xs)),
        'variants': sum(a.get('variants') or 1 for a in xs), 'bestScore': max(a['score'] for a in xs),
        'bestAd': max(xs, key=lambda a: a['score'])['id'], 'newLast14': sum(1 for a in xs if a['daysLive'] <= 14),
        'domains': sorted({a.get('domain') for a in xs if a.get('domain')}),
        'shopify': any(a.get('shopPlatform') == 'Shopify' for a in xs),
    } for k, xs in pages.items()], key=lambda r: (-r['bestScore'], -r['ads']))

    # 商品排行（落地页商品）+ 同款竞争：同一个商品名被多家店推
    prods = collections.defaultdict(list)
    for a in ads:
        if a.get('productKey'):
            prods[a['productKey']].append(a)
    rows = []
    for k, xs in prods.items():
        p = next((a['product'] for a in xs if a.get('product')), {}) or {}
        handle = k.split('/products/')[-1]
        rows.append({'key': k, 'domain': xs[0].get('domain'), 'handle': handle, 'title': p.get('title') or handle.replace('-', ' '),
                     'price': p.get('price'), 'compareAt': p.get('compareAt'), 'image': p.get('image'), 'createdAt': p.get('createdAt'),
                     'variants': p.get('variants'), 'ads': len(xs), 'pages': sorted({a.get('pageName') for a in xs if a.get('pageName')}),
                     'maxDays': max(a['daysLive'] for a in xs), 'bestScore': max(a['score'] for a in xs), 'url': xs[0].get('linkUrl'),
                     'adIds': [a['id'] for a in sorted(xs, key=lambda a: -a['score'])][:12]})
    out['products'] = sorted(rows, key=lambda r: (-r['bestScore'], -r['ads']))
    out['prices'] = sorted(r['price'] for r in rows if r.get('price'))

    def stem(h):  # 用 handle 去掉尾部数字/颜色等后缀，粗略归并“同款”
        h = re.sub(r'(-\d+|-(copy|new|sale|us|usa|uk|official|v\d))+$', '', h)
        return ' '.join(w for w in h.split('-') if w not in STOP)[:60]
    same = collections.defaultdict(list)
    for r in rows:
        same[stem(r['handle'])].append(r)
    out['sameProduct'] = sorted([{'name': k, 'shops': sorted({r['domain'] for r in rs}), 'ads': sum(r['ads'] for r in rs),
                                  'prices': sorted(r['price'] for r in rs if r.get('price')), 'keys': [r['key'] for r in rs]}
                                 for k, rs in same.items() if k and len({r['domain'] for r in rs}) >= 2],
                                key=lambda g: -len(g['shops']))
    # 同一段文案被多家主页使用（多是铺货/同源素材）
    bodies = collections.defaultdict(list)
    for a in ads:
        nb = _norm_body(a.get('body'))
        if len(nb) > 40:
            bodies[nb].append(a)
    out['sameCopy'] = sorted([{'snippet': xs[0]['body'][:160], 'pages': sorted({a.get('pageName') for a in xs}), 'adIds': [a['id'] for a in xs][:20]}
                              for xs in bodies.values() if len({a.get('pageId') for a in xs}) >= 2], key=lambda g: -len(g['pages']))
    return out


def media_aggregate(ads, out):
    """素材下载处理完之后再补的统计：视频时长、剪辑节奏、画幅、同图多店铺。"""
    vids = [a['video'] for a in ads if (a.get('video') or {}).get('seconds')]
    if vids:
        secs = [v['seconds'] for v in vids]
        out['video'] = {'count': len(vids), 'medianSeconds': round(statistics.median(secs), 1),
                        'lengths': dict(collections.Counter('≤15s' if s <= 15 else ('16–30s' if s <= 30 else ('31–60s' if s <= 60 else '>60s')) for s in secs)),
                        'medianShot': round(statistics.median(v['avgShot'] for v in vids if v.get('avgShot')), 2) if any(v.get('avgShot') for v in vids) else None,
                        'aspects': dict(collections.Counter(v.get('aspect') or '?' for v in vids)),
                        'withVoice': sum(1 for v in vids if (v.get('transcript') or {}).get('text'))}
    imgs = [a['imageInfo'] for a in ads if a.get('imageInfo')]
    if imgs:
        out['image'] = {'count': len(imgs), 'aspects': dict(collections.Counter(i.get('aspect') or '?' for i in imgs)),
                        'tones': dict(collections.Counter(i.get('tone') or '?' for i in imgs))}
    groups = collections.defaultdict(list)
    for a in ads:
        h = (a.get('imageInfo') or {}).get('hash') or (a.get('video') or {}).get('hash')
        if h:
            groups[h].append(a)
    out['sameCreative'] = sorted([{'pages': sorted({a.get('pageName') for a in xs}), 'adIds': [a['id'] for a in xs][:20], 'thumb': xs[0].get('thumb')}
                                  for xs in groups.values() if len({a.get('pageId') for a in xs}) >= 2], key=lambda g: -len(g['pages']))
    return out
