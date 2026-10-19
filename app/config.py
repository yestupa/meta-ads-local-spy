"""路径、设置读写、国家列表。设置保存在 data/settings.json（只存在本机，不要分享这个文件）。"""
import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
JOBS = os.path.join(DATA, 'jobs')
SETTINGS_PATH = os.path.join(DATA, 'settings.json')
WEB = os.path.join(ROOT, 'app', 'web')

# Meta 广告资料库的国家参数（ISO 两位代码；ALL = 全部国家）
COUNTRIES = {
    'US': '美国', 'GB': '英国', 'CA': '加拿大', 'AU': '澳大利亚', 'NZ': '新西兰', 'DE': '德国', 'FR': '法国',
    'IT': '意大利', 'ES': '西班牙', 'NL': '荷兰', 'SE': '瑞典', 'PL': '波兰', 'IE': '爱尔兰', 'JP': '日本',
    'KR': '韩国', 'SG': '新加坡', 'MY': '马来西亚', 'PH': '菲律宾', 'TH': '泰国', 'AE': '阿联酋', 'SA': '沙特',
    'BR': '巴西', 'MX': '墨西哥', 'ALL': '全部国家',
}

MODELS = {
    'claude-opus-5-5': 'Claude Opus 5.5（分析最细，较贵）',
    'claude-sonnet-5-5': 'Claude Sonnet 5.5（推荐，性价比高）',
    'claude-haiku-5-5': 'Claude Haiku 5.5（最便宜，分析较浅）',
}

ENGINES = {
    'claude_code': 'Claude Code（用你的 Claude 订阅，不需要 API key）',
    'api': 'Claude API（需要 API key，按量付费）',
    'none': '不做 AI 分析（只抓取 + 本地分析）',
}
CC_MODELS = {'sonnet': 'Sonnet（推荐）', 'opus': 'Opus（分析更细，更耗额度）', 'haiku': 'Haiku（最快、最省额度）'}
WHISPER_MODELS = {'tiny': 'tiny（最快）', 'base': 'base', 'small': 'small（推荐）', 'medium': 'medium（最准，较慢）'}

DEFAULTS = {
    'engine': 'claude_code',
    'cc_model': 'sonnet',
    'api_key': '',
    'model': 'claude-sonnet-5-5',
    'effort': 'medium',
    'country': 'US',
    'depth': 'standard',        # quick / standard / deep：每个关键词查询资料库的次数
    'proxy': '',                # 例如 http://127.0.0.1:7890 ；留空使用系统代理
    'show_browser': False,
    'max_videos': 20,           # 下载并拆解（分镜、转写）的视频数，按爆款指数从高到低
    'max_images': 80,           # 下载的图片数
    'ai_top_n': 12,             # AI 深度拆解（画面 + 脚本）的素材数
    'transcribe': True,         # 视频语音转写（需要 faster-whisper）
    'whisper_model': 'small',
    'shop_enrich': True,        # 读取 Shopify 落地页的商品名、售价、原价
    'auto_analyze': True,
}

_lock = threading.Lock()


def ensure_dirs():
    from .util import check_bundle
    check_bundle()
    for d in (DATA, JOBS):
        os.makedirs(d, exist_ok=True)


def load_settings():
    ensure_dirs()
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding='utf-8') as f:
                s.update(json.load(f))
        except ValueError:
            pass
    if not s.get('api_key') and os.environ.get('ANTHROPIC_API_KEY'):
        s['api_key'] = os.environ['ANTHROPIC_API_KEY']
        s['api_key_from_env'] = True
    return s


def save_settings(new):
    with _lock:
        cur = load_settings()
        cur.pop('api_key_from_env', None)
        for k, v in new.items():
            if k not in DEFAULTS:
                continue
            if k == 'api_key' and (v is None or str(v).startswith('••')):
                continue  # 面板上显示的是打码后的值，没改就不覆盖
            if isinstance(DEFAULTS[k], bool):
                v = bool(v)
            elif isinstance(DEFAULTS[k], int):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    continue
            cur[k] = v
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(cur, f, ensure_ascii=False, indent=1)
    return load_settings()


def public_settings():
    s = load_settings()
    key = s.get('api_key') or ''
    s['api_key'] = ('••••••••' + key[-4:]) if key else ''
    s['has_api_key'] = bool(key)
    s.update(countries=COUNTRIES, models=MODELS, engines=ENGINES, cc_models=CC_MODELS, whisper_models=WHISPER_MODELS)
    return s
