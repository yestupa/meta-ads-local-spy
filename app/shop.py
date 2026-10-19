"""落地页商品信息：广告落地页是 Shopify 商品页（/products/<handle>）时，读取公开的 <商品页>.js，拿到商品名、售价、原价、上架时间。
这是 Shopify 店铺对所有访客公开的接口，只做 GET 读取，不下单、不加购。"""
import json
import re
import urllib.parse

from .util import host_of


def product_ref(url):
    """返回 (店铺域名, 商品 handle)；不是 /products/ 链接时 handle 为 None。"""
    if not url:
        return None, None
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return None, None
    host = host_of(url)
    if not host or host.endswith(('facebook.com', 'instagram.com', 'fb.me', 'm.me', 'whatsapp.com')):
        return host or None, None
    m = re.search(r'/products/([^/?#]+)', p.path or '')
    return host, (urllib.parse.unquote(m.group(1)).lower() if m else None)


def _fetch(page, host, handle):
    """用浏览器标签页打开 .js：Shopify 会对 Python/Node 的 HTTP 客户端返回 429（按 TLS 指纹识别），真实浏览器可以正常读取。"""
    r = page.goto(f'https://{host}/products/{urllib.parse.quote(handle)}.js', wait_until='domcontentloaded', timeout=20000)
    if not r or r.status != 200:
        return None
    try:
        d = json.loads(page.evaluate('document.body.innerText'))
    except ValueError:
        return None
    if not isinstance(d, dict) or 'price' not in d:
        return None
    cents = lambda v: round(v / 100, 2) if isinstance(v, (int, float)) and v else None
    img = d.get('featured_image') or ((d.get('images') or [None])[0])
    if img and img.startswith('//'):
        img = 'https:' + img
    return {'title': d.get('title'), 'vendor': d.get('vendor'), 'type': d.get('type'),
            'price': cents(d.get('price_min') or d.get('price')), 'priceMax': cents(d.get('price_max')),
            'compareAt': cents(d.get('compare_at_price_min') or d.get('compare_at_price')),
            'variants': len(d.get('variants') or []), 'available': d.get('available'),
            'createdAt': (d.get('created_at') or '')[:10] or None, 'publishedAt': (d.get('published_at') or '')[:10] or None,
            'image': img, 'tags': (d.get('tags') or [])[:12] if isinstance(d.get('tags'), list) else []}


def enrich(page, ads, log, progress, check, limit=50):
    refs = {}
    for a in ads:
        host, handle = product_ref(a.get('linkUrl'))
        a['domain'] = host
        if handle:
            a['productKey'] = f'{host}/products/{handle}'
            refs.setdefault((host, handle), []).append(a)
    # 先查被最多广告指向的商品；同一家店连续失败 2 次（不是 Shopify 或被拦）就不再试
    todo = sorted(refs.items(), key=lambda kv: -len(kv[1]))[:limit]
    products, shopify_hosts, bad = {}, set(), {}
    for i, ((h, hd), _) in enumerate(todo):
        check()
        if bad.get(h, 0) >= 2:
            continue
        progress(f'读取商品页 {i + 1}/{len(todo)}：{h}')
        try:
            info = _fetch(page, h, hd)
        except Exception:
            info = None
        if info:
            shopify_hosts.add(h)
            products[f'{h}/products/{hd}'] = info
        else:
            bad[h] = bad.get(h, 0) + 1
    for a in ads:
        if a.get('productKey') in products:
            a['product'] = products[a['productKey']]
        if a.get('domain') in shopify_hosts:
            a['shopPlatform'] = 'Shopify'
    log(f'落地页：{len(refs)} 个商品页，读到 {len(products)} 个 Shopify 商品的价格（{len(shopify_hosts)} 家店）')
    return products
