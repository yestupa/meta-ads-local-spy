"""品牌模式：识别品牌的官方主页，只抓这个主页的广告。

主页视图同样每次只返回 30 条（未登录时翻页接口会被限流），所以：
1. 先跑多组 排序 × 形式 × 平台 组合；
2. 再用“主页内搜索”滚雪球：从已抓到的文案里挑高频词（dog / litter / pharmacy…）逐个在主页内搜索，每个词又是不同的 30 条，
   直到搜索词用完或连续几个词都没有新广告。
"""
import collections
import math
import re
import time
import urllib.parse

from .i18n import T
from .meta import LIB, MetaError, _open_list, list_url
from .util import host_of, registrable

PAGE_BASE = [
    ('主页 · 曝光最高', {'sort': 'total_impressions', 'media': 'all'}),
    ('主页 · 最新上线', {'sort': 'relevancy_monthly_grouped', 'media': 'all'}),
    ('主页 · 视频 · 曝光最高', {'sort': 'total_impressions', 'media': 'video'}),
    ('主页 · 图片 · 曝光最高', {'sort': 'total_impressions', 'media': 'image'}),
    ('主页 · 视频 · 最新', {'sort': 'relevancy_monthly_grouped', 'media': 'video'}),
    ('主页 · 图片 · 最新', {'sort': 'relevancy_monthly_grouped', 'media': 'image'}),
    ('主页 · 图文 · 曝光最高', {'sort': 'total_impressions', 'media': 'meme'}),
    ('主页 · Audience Network', {'sort': 'total_impressions', 'media': 'all', 'platform': 'audience_network'}),
    ('主页 · Messenger', {'sort': 'total_impressions', 'media': 'all', 'platform': 'messenger'}),
    ('主页 · 图文 · 最新', {'sort': 'relevancy_monthly_grouped', 'media': 'meme'}),
]
# 每种深度：(基础组合数, 主页内搜索词上限)
PAGE_DEPTHS = {'quick': (4, 2), 'standard': (8, 10), 'deep': (10, 30)}
SEED_STOP = set("""the and for you your with our this that are from all get now off shop more new free just out can has have was will not but
what when how its it's who why one two any each into than then them they their there here also only over very much most best save order
today deal deals sale code use using used need want make made like love find every first back day days week weeks time ever still well good
great https www com amp low high support help helps keep give right perfect favorite everything anything available
limited shipping orders link bio click tap""".split())


def _label(label):
    """查询标签（内部用中文）翻译成当前语言，用于日志。"""
    if label.startswith('主页内搜索 · '):
        return T('主页内搜索 · {term}', term=label.split(' · ', 1)[1])
    return T(label)


def page_url(country, page_id, sort='total_impressions', media='all', platform=None, q=None, active_only=True):
    p = {'active_status': 'active' if active_only else 'all', 'ad_type': 'all', 'country': country, 'is_targeted_country': 'false',
         'media_type': media, 'search_type': 'keyword_unordered' if q else 'page', 'view_all_page_id': page_id,
         'sort_data[mode]': sort, 'sort_data[direction]': 'desc'}
    if q:
        p['q'] = q
    if platform:
        p['publisher_platforms[0]'] = platform
    return LIB + '?' + urllib.parse.urlencode(p)


def norm_name(s):
    s = (s or '').lower().replace('’', "'")
    s = re.sub(r"'s\b", '', s)
    return re.sub(r'[^a-z0-9]+', '', s)


def parse_input(text):
    """品牌输入可以是：主页 ID / 主页链接 / 域名 / 品牌名。"""
    t = (text or '').strip()
    if re.fullmatch(r'\d{6,20}', t):
        return {'kind': 'id', 'value': t, 'name': None, 'domain': None, 'slug': None}
    m = re.search(r'facebook\.com/(?:profile\.php\?id=(\d+)|(?:pg/)?([A-Za-z0-9.\-_]+))', t)
    if m:
        if m.group(1):
            return {'kind': 'id', 'value': m.group(1), 'name': None, 'domain': None, 'slug': None}
        return {'kind': 'slug', 'value': t, 'name': m.group(2), 'domain': None, 'slug': m.group(2).lower()}
    m = re.match(r'(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)', t.lower())
    if m and '.' in t and ' ' not in t:
        dom = m.group(1)
        return {'kind': 'domain', 'value': t, 'name': dom.split('.')[0], 'domain': dom, 'slug': None}
    return {'kind': 'name', 'value': t, 'name': t, 'domain': None, 'slug': None}


def identify(page, text, country, log, progress):
    """按品牌名/域名搜索资料库，给出现的每个主页打分：名称一致、主页链接一致、落地页是品牌域名、粉丝数。返回 (最佳, 候选列表)。"""
    b = parse_input(text)
    if b['kind'] == 'id':
        return {'pageId': b['value'], 'pageName': None, 'score': 100, 'reasons': [T('直接指定的主页 ID')]}, []
    terms = [b['name']] + ([b['domain']] if b.get('domain') else [])
    pages = {}
    for term in terms:
        for sort in ('total_impressions', 'relevancy_monthly_grouped'):
            progress(T('正在识别“{t}”的官方主页（搜索 {s}）', t=text, s=term))
            try:
                _, ads = _open_list(page, list_url(country, term, sort=sort, active_only=False))
            except MetaError:
                raise
            except Exception as e:
                log(T('识别主页时查询失败（{s}）：{e}', s=term, e=str(e)[:120]))
                continue
            for a in ads:
                p = pages.setdefault(a['pageId'], {'pageId': a['pageId'], 'pageName': a['pageName'], 'pageUrl': a.get('pageUrl'),
                                                   'likes': 0, 'avatar': a.get('pageAvatar'), 'ads': 0, 'domains': collections.Counter()})
                p['ads'] += 1
                p['likes'] = max(p['likes'], a.get('pageLikes') or 0)
                if a.get('linkUrl'):
                    p['domains'][registrable(host_of(a['linkUrl']))] += 1
            time.sleep(1.2)
    want = norm_name(b['name'])
    want_dom = registrable(b['domain']) if b.get('domain') else None
    out = []
    for p in pages.values():
        score, why = 0, []
        nn = norm_name(p['pageName'])
        slug = ((p.get('pageUrl') or '').rstrip('/').split('/')[-1]).lower()
        if nn == want:
            score += 50
            why.append(T('主页名称与品牌一致'))
        elif want and (nn.startswith(want) or nn.endswith(want)) and len(nn) <= len(want) + 8:
            score += 25
            why.append(T('主页名称包含品牌名'))
        if b.get('slug') and slug == b['slug']:
            score += 60
            why.append(T('主页链接一致'))
        elif want and norm_name(slug) == want:
            score += 20
            why.append(T('主页链接名与品牌一致'))
        if want_dom:
            hits = p['domains'].get(want_dom, 0)
        else:
            hits = sum(v for d, v in p['domains'].items() if norm_name(d.split('.')[0]) == want)
        if hits:
            score += round(25 * hits / max(sum(p['domains'].values()), 1))
            why.append(T('{n} 条广告落地到品牌域名', n=hits))
        if p['likes']:
            score += min(15, round(math.log10(p['likes'] + 1) * 2.5))
            why.append(T('{n} 粉丝', n=f'{p["likes"]:,}'))
        out.append(dict(p, score=score, reasons=why, domains=dict(p['domains'].most_common(3))))
    out.sort(key=lambda p: (-p['score'], -p['likes']))
    if not out:
        return None, []
    best = out[0]
    log(T('识别主页：{n}（{id}），得分 {s}：{r}', n=best['pageName'], id=best['pageId'], s=best['score'], r=T('；').join(best['reasons'])))
    return best, out[:8]


def _seed_terms(ads, used, skip, n):
    df = collections.Counter()
    for a in ads:
        text = ' '.join(x for x in (a.get('title'), a.get('body'), a.get('linkDescription')) if x).lower()
        df.update(w for w in set(re.findall(r"[a-z][a-z'-]{2,}", text)) if w not in SEED_STOP and w not in skip)
    return [w for w, c in df.most_common(300) if w not in used and c >= 2][:n]


def collect(page, page_id, brand_name, country, depth, active_only, extra_terms, log, progress, check):
    """返回 {'ads', 'queries', 'pageTotal'}。只保留这个主页自己的广告。"""
    n_base, n_seed = PAGE_DEPTHS.get(depth) or PAGE_DEPTHS['standard']
    ads, queries, state = {}, [], {'total': None, 'empty': 0}
    skip = set(re.findall(r'[a-z]+', (brand_name or '').lower())) | {norm_name(brand_name)}

    def run(label, url, kind):
        check()
        try:
            t, got = _open_list(page, url)
        except MetaError:
            raise
        except Exception as e:
            log(T('查询失败 {label}：{e}', label=_label(label), e=str(e).splitlines()[0][:150]))
            queries.append({'keyword': brand_name, 'label': label, 'url': url, 'total': None, 'got': 0, 'new': 0, 'error': str(e)[:150]})
            return 0
        if kind == 'imp_all':
            state['total'] = t
        new = 0
        for pos, a in enumerate(got, 1):
            if a['pageId'] != str(page_id):
                continue  # 主页内搜索偶尔混进合作/达人主页的广告
            cur = ads.get(a['id'])
            if not cur:
                cur = ads[a['id']] = dict(a, hits=[], keywords=[brand_name])
                new += 1
            cur['hits'].append(label)
            if kind == 'imp_all':
                cur['impRank'] = min(cur.get('impRank') or 99, pos)
            elif kind == 'imp':
                cur['impRankOther'] = min(cur.get('impRankOther') or 99, pos)
            else:
                cur['newRank'] = min(cur.get('newRank') or 99, pos)
        queries.append({'keyword': brand_name, 'label': label, 'url': url, 'total': t, 'got': len(got), 'new': new})
        log(T('{label}：共 {t} 条，拿到 {g} 条，新增 {n} 条（累计 {c}）', label=_label(label), t=t if t is not None else '?', g=len(got), n=new, c=len(ads)))
        state['empty'] = state['empty'] + 1 if not got else 0
        if state['empty'] >= 3:
            raise MetaError(T('连续 3 次查询没有返回广告，可能被 Meta 暂时限流。过一会儿再试，或换一个代理节点'))
        time.sleep(1.5)
        return new

    for i, (label, p) in enumerate(PAGE_BASE[:n_base]):
        progress(T('{label}（{i}/{n}）· 已拿到 {c} 条', label=T(label), i=i + 1, n=n_base, c=len(ads)))
        kind = ('imp_all' if i == 0 else 'imp') if p['sort'] == 'total_impressions' else 'new'
        run(label, page_url(country, page_id, p['sort'], p['media'], p.get('platform'), active_only=active_only), kind)
    used, weak, done = set(), 0, 0
    terms = [t.strip().lower() for t in extra_terms if t.strip()]
    limit = n_seed + len(terms)
    while done < limit:
        if not terms:
            terms = _seed_terms(list(ads.values()), used, skip, 5)
            if not terms:
                break
        term = terms.pop(0)
        if term in used:
            continue
        used.add(term)
        done += 1
        progress(T('主页内搜索“{t}”（{d}/{l}）· 已拿到 {n} 条', t=term, d=done, l=limit, n=len(ads)))
        new = run(f'主页内搜索 · {term}', page_url(country, page_id, q=term, active_only=active_only), 'imp')
        weak = weak + 1 if new < 3 else 0
        if weak >= 4:
            log(T('连续 4 个搜索词几乎没有新广告，停止主页内搜索'))
            break
    return {'ads': list(ads.values()), 'queries': queries, 'pageTotal': state['total']}
