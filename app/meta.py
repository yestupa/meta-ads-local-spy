"""按关键词采集 Meta 广告资料库（Facebook / Instagram / Messenger / Audience Network）。

数据来源：资料库列表页内嵌的首屏 JSON（结构化字段：文案、标题、视频/图片地址、落地页、CTA、上线日期、同素材广告数……）。
未登录时，滚动翻页的接口会返回 “Rate limit exceeded”，所以每次打开只能拿到 30 条。
为了一个关键词拿到更多素材，这里用多组查询（按曝光 / 按最新 × 全部 / 视频 / 图片 × 平台）分别打开，再合并去重。
在“按曝光排序”列表里的位置（impRank）是资料库能给出的最接近“跑量”的信号。
"""
import re
import time
import urllib.parse

from .util import extract_json_objects_containing, ts_date

LIB = 'https://www.facebook.com/ads/library/'

# (标签, 参数)。sort: total_impressions = 总曝光降序；relevancy_monthly_grouped = 实测为最新上线在前
Q_IMP_ALL = ('曝光最高 · 全部', {'sort': 'total_impressions', 'media': 'all'})
Q_IMP_VIDEO = ('曝光最高 · 视频', {'sort': 'total_impressions', 'media': 'video'})
Q_IMP_IMAGE = ('曝光最高 · 图片', {'sort': 'total_impressions', 'media': 'image'})
Q_NEW_ALL = ('最新上线 · 全部', {'sort': 'relevancy_monthly_grouped', 'media': 'all'})
Q_NEW_VIDEO = ('最新上线 · 视频', {'sort': 'relevancy_monthly_grouped', 'media': 'video'})
Q_NEW_IMAGE = ('最新上线 · 图片', {'sort': 'relevancy_monthly_grouped', 'media': 'image'})
Q_IMP_IG = ('曝光最高 · Instagram', {'sort': 'total_impressions', 'media': 'all', 'platform': 'instagram'})
Q_IMP_FB = ('曝光最高 · Facebook', {'sort': 'total_impressions', 'media': 'all', 'platform': 'facebook'})
Q_NEW_IG = ('最新上线 · Instagram', {'sort': 'relevancy_monthly_grouped', 'media': 'all', 'platform': 'instagram'})
Q_EXACT = ('曝光最高 · 精确词组', {'sort': 'total_impressions', 'media': 'all', 'exact': True})

DEPTHS = {
    'quick': [Q_IMP_ALL, Q_NEW_ALL],
    'standard': [Q_IMP_ALL, Q_IMP_VIDEO, Q_IMP_IMAGE, Q_NEW_ALL, Q_NEW_VIDEO, Q_IMP_IG],
    'deep': [Q_IMP_ALL, Q_IMP_VIDEO, Q_IMP_IMAGE, Q_NEW_ALL, Q_NEW_VIDEO, Q_NEW_IMAGE, Q_IMP_IG, Q_IMP_FB, Q_NEW_IG, Q_EXACT],
}
DEPTH_LABEL = {'quick': '快速（每个词 2 次查询，约 60 条）', 'standard': '标准（每个词 6 次查询，约 120–180 条）',
               'deep': '深度（每个词 10 次查询，约 200–300 条）'}


class MetaError(RuntimeError):
    pass


def list_url(country, keyword, sort='total_impressions', media='all', platform=None, exact=False, active_only=True):
    q = {'active_status': 'active' if active_only else 'all', 'ad_type': 'all', 'country': country,
         'is_targeted_country': 'false', 'media_type': media, 'q': keyword,
         'search_type': 'keyword_exact_phrase' if exact else 'keyword_unordered',
         'sort_data[mode]': sort, 'sort_data[direction]': 'desc'}
    if platform:
        q['publisher_platforms[0]'] = platform
    return LIB + '?' + urllib.parse.urlencode(q)


def _clean(s):
    s = (s or '').strip() if isinstance(s, str) else ''
    return '' if '{{' in s else s  # 动态素材（DCO/DPA）的模板占位符，如 {{product.brand}}


def norm_ad(n):
    s = n.get('snapshot') or {}
    cards = s.get('cards') or []
    is_vid = lambda c: c.get('video_hd_url') or c.get('video_sd_url')
    body = _clean((s.get('body') or {}).get('text'))
    title = _clean(s.get('title'))
    if cards:
        body = body or next((_clean(c.get('body')) for c in cards if _clean(c.get('body'))), '')
        title = title or next((_clean(c.get('title')) for c in cards if _clean(c.get('title'))), '')
    videos = [v for v in (s.get('videos') or []) if is_vid(v)] + [c for c in cards if is_vid(c)]
    images = [i.get('original_image_url') or i.get('resized_image_url') for i in (s.get('images') or [])]
    images += [c.get('original_image_url') or c.get('resized_image_url') for c in cards if not is_vid(c)]
    link = s.get('link_url') or next((c.get('link_url') for c in cards if c.get('link_url')), None)
    bc = s.get('branded_content') or {}
    return {
        'id': str(n['ad_archive_id']),
        'pageId': str(n.get('page_id') or ''),
        'pageName': n.get('page_name'),
        'pageUrl': s.get('page_profile_uri'),
        'pageAvatar': s.get('page_profile_picture_url'),
        'pageLikes': s.get('page_like_count'),
        'pageCategories': s.get('page_categories') or [],
        'creatorPage': s.get('page_name') if bc and s.get('page_name') != n.get('page_name') else None,
        'isActive': n.get('is_active'),
        'startDate': str(ts_date(n.get('start_date'))) if n.get('start_date') else None,
        'endDate': str(ts_date(n.get('end_date'))) if n.get('end_date') else None,
        'variants': n.get('collation_count') or 1,  # “N 条广告使用了这个素材和文案”
        'collationId': n.get('collation_id'),
        'platforms': n.get('publisher_platform') or [],
        'countries': n.get('targeted_or_reached_countries') or [],
        'format': s.get('display_format'),
        'body': body,
        'title': title,
        'linkDescription': _clean(s.get('link_description')),
        'caption': s.get('caption'),
        'linkUrl': link,
        'cta': s.get('cta_text') or next((c.get('cta_text') for c in cards if c.get('cta_text')), None),
        'ctaType': s.get('cta_type'),
        'videos': [{'hd': v.get('video_hd_url'), 'sd': v.get('video_sd_url'), 'poster': v.get('video_preview_image_url')} for v in videos],
        'images': [u for u in images if u],
        'cards': [{'title': _clean(c.get('title')), 'body': _clean(c.get('body')), 'linkUrl': c.get('link_url'), 'cta': c.get('cta_text'),
                   'image': c.get('original_image_url') or c.get('resized_image_url') or c.get('video_preview_image_url'),
                   'isVideo': bool(is_vid(c))} for c in cards[:10]],
        'libraryUrl': f'https://www.facebook.com/ads/library/?id={n["ad_archive_id"]}',
    }


def _open_list(page, url):
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(4500)
    if '/login' in page.url or 'checkpoint' in page.url:
        raise MetaError('Facebook 跳转到了登录/验证页面。换一个代理节点，或者过一会儿再试')
    html = page.content()
    if 'xfb_ad_library_is_captcha_required":true' in html:
        raise MetaError('Meta 要求验证码。在设置里勾选“显示浏览器窗口”后重试，手动完成验证；或者换一个代理节点')
    m = re.search(r'"search_results_connection":\{"count":(\d+)', html)
    ads, seen = [], set()
    for n in extract_json_objects_containing(html, 'ad_archive_id'):
        if n.get('ad_archive_id') and 'snapshot' in n and n['ad_archive_id'] not in seen:
            seen.add(n['ad_archive_id'])
            ads.append(norm_ad(n))
    return (int(m.group(1)) if m else None), ads


def collect(page, keywords, country, depth, active_only, log, progress, check):
    """返回 {'ads': [...], 'queries': [...], 'totals': {关键词: 资料库里的在投总数}}。"""
    variants = DEPTHS.get(depth) or DEPTHS['standard']
    ads, queries, totals = {}, [], {}
    n_total = len(keywords) * len(variants)
    empty_streak = 0
    for ki, kw in enumerate(keywords):
        for vi, (label, p) in enumerate(variants):
            check()
            idx = ki * len(variants) + vi + 1
            progress(f'“{kw}” · {label}（{idx}/{n_total}）')
            url = list_url(country, kw, p['sort'], p['media'], p.get('platform'), p.get('exact'), active_only)
            try:
                total, got = _open_list(page, url)
            except MetaError:
                raise
            except Exception as e:
                log(f'查询失败 {kw} · {label}：{str(e).splitlines()[0][:150]}')
                queries.append({'keyword': kw, 'label': label, 'url': url, 'total': None, 'got': 0, 'new': 0, 'error': str(e)[:150]})
                continue
            if label == Q_IMP_ALL[0]:
                totals[kw] = total
            new = 0
            for pos, a in enumerate(got, 1):
                cur = ads.get(a['id'])
                if not cur:
                    cur = ads[a['id']] = dict(a, hits=[], keywords=[])
                    new += 1
                cur['hits'].append(label)
                if kw not in cur['keywords']:
                    cur['keywords'].append(kw)
                if p['sort'] == 'total_impressions':
                    key = 'impRank' if p['media'] == 'all' and not p.get('platform') and not p.get('exact') else 'impRankOther'
                    cur[key] = min(cur.get(key) or 99, pos)
                else:
                    cur['newRank'] = min(cur.get('newRank') or 99, pos)
            queries.append({'keyword': kw, 'label': label, 'url': url, 'total': total, 'got': len(got), 'new': new})
            log(f'{kw} · {label}：资料库共 {total if total is not None else "?"} 条，本次拿到 {len(got)} 条，新增 {new} 条')
            empty_streak = empty_streak + 1 if not got else 0
            if empty_streak >= 3:
                log('连续 3 次查询没有返回广告，可能被 Meta 限流，提前结束采集')
                return {'ads': list(ads.values()), 'queries': queries, 'totals': totals, 'stoppedEarly': True}
            time.sleep(1.5)
    return {'ads': list(ads.values()), 'queries': queries, 'totals': totals, 'stoppedEarly': False}
