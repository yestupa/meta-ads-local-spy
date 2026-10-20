"""素材本地化与本地分析：
- 所有广告：下载缩略图（视频封面或首图），算主色、画幅、明暗和感知哈希（用于找“同一素材被多家店铺使用”）；
- 爆款指数靠前的图片广告：下载全部图片（轮播最多 6 张）；
- 爆款指数靠前的视频广告：下载视频，算时长、画幅、切镜次数和平均镜头时长，生成逐秒分镜图、前 3 秒钩子帧，并做语音转写（带时间戳）。
Facebook 的素材地址带过期参数，所以全部存到本地，面板和导出报告都读本地文件。"""
import io
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageStat

from .i18n import T
from .util import download

THUMB_W = 480


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def has_ffmpeg():
    try:
        return os.path.exists(_ff())
    except Exception:
        return False


def _aspect(w, h):
    if not w or not h:
        return None
    r = w / h
    for lab, v in (('9:16', 9 / 16), ('4:5', 4 / 5), ('1:1', 1), ('16:9', 16 / 9), ('1.91:1', 1.91)):
        if abs(r - v) < 0.06:
            return lab
    return f'{w}x{h}'


def image_info(im):
    """主色（5 个）、画幅、明暗、感知哈希（8x8 平均哈希）。"""
    im = im.convert('RGB')
    w, h = im.size
    small = im.resize((96, max(1, int(96 * h / w))))
    q = small.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:15]
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    colors = [{'hex': '#%02x%02x%02x' % tuple(pal[i * 3:i * 3 + 3]), 'pct': round(c / total * 100)} for c, i in counts if i * 3 + 2 < len(pal)]
    lum = ImageStat.Stat(small.convert('L')).mean[0]
    sat = ImageStat.Stat(small.convert('HSV')).mean[1]
    g = im.convert('L').resize((8, 8))
    px = list(g.getdata())
    avg = sum(px) / 64
    bits = ''.join('1' if p > avg else '0' for p in px)
    return {'w': w, 'h': h, 'aspect': _aspect(w, h), 'colors': colors, 'brightness': round(lum),
            'tone': ('偏暗' if lum < 85 else ('明亮' if lum > 170 else '中等')) + ('·高饱和' if sat > 120 else ('·低饱和' if sat < 45 else '')),
            'hash': '%016x' % int(bits, 2)}


def save_thumb(src, dst, width=THUMB_W):
    im = Image.open(src).convert('RGB')
    info = image_info(im)
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, quality=84)
    return info


# ---------------- 视频 ----------------
def probe(video):
    err = subprocess.run([_ff(), '-i', video], capture_output=True, text=True, errors='ignore').stderr
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    d = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0
    s = re.search(r'Video:.*?, (\d{2,5})x(\d{2,5})', err)
    w, h = (int(s[1]), int(s[2])) if s else (None, None)
    return d, w, h, ('Audio:' in err)


def frame(video, t, width):
    out = subprocess.run([_ff(), '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1',
                          '-vf', f'scale={width}:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(out)).convert('RGB') if out else None


def grid(frames, labels, per_row, out):
    frames = [(f, l) for f, l in zip(frames, labels) if f is not None]
    if not frames:
        return None
    w, h = frames[0][0].size
    rows = (len(frames) + per_row - 1) // per_row
    sheet = Image.new('RGB', (w * min(per_row, len(frames)), h * rows), 'white')
    for i, (im, lab) in enumerate(frames):
        im = im.resize((w, h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 50, 15], fill='black')
        d.text((3, 2), lab, fill='yellow')
        sheet.paste(im, ((i % per_row) * w, (i // per_row) * h))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out, quality=82)
    return out


def scene_cuts(video, threshold=0.28):
    err = subprocess.run([_ff(), '-i', video, '-vf', f"select='gt(scene,{threshold})',showinfo", '-an', '-f', 'null', '-'],
                         capture_output=True, text=True, errors='ignore').stderr
    return [round(float(x), 2) for x in re.findall(r'pts_time:([\d.]+)', err)]


_whisper = {}


def whisper_ok():
    try:
        import faster_whisper  # noqa
        return True
    except Exception:
        return False


def transcribe(video, model_size='small'):
    import numpy as np
    pcm = subprocess.run([_ff(), '-loglevel', 'error', '-i', video, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    if len(pcm) < 32000:
        return {'text': '', 'lang': None, 'segments': []}
    if model_size not in _whisper:
        from faster_whisper import WhisperModel
        _whisper[model_size] = WhisperModel(model_size, device='cpu', compute_type='int8')
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, info = _whisper[model_size].transcribe(audio, vad_filter=True)
    segs = [{'t': round(s.start, 1), 'end': round(s.end, 1), 'text': s.text.strip()} for s in segs if s.text.strip()]
    return {'text': ' '.join(s['text'] for s in segs), 'lang': info.language, 'segments': segs}


def process_video(path, out_dir, rel_dir, stem, do_transcribe, whisper_model):
    d, w, h, has_audio = probe(path)
    cuts = [c for c in scene_cuts(path) if c < d - 0.05]
    v = {'seconds': round(d, 1), 'w': w, 'h': h, 'aspect': _aspect(w, h), 'hasAudio': has_audio, 'cuts': cuts,
         'shots': len(cuts) + 1, 'avgShot': round(d / (len(cuts) + 1), 2) if d else None,
         'pace': None}
    if v['avgShot']:
        v['pace'] = '快剪（平均 <1.5 秒一个镜头）' if v['avgShot'] < 1.5 else ('中等（1.5–3 秒）' if v['avgShot'] <= 3 else '慢节奏（>3 秒）')
    # 逐秒分镜 + 切镜点后 0.15 秒各一帧（最多 40 帧）
    ts = sorted(set([float(t) for t in range(0, int(d))] + [round(c + 0.15, 2) for c in cuts]))
    ts = [t for t in ts if t < d - 0.05][:40]
    if grid([frame(path, t, 180) for t in ts], [f'{t:.1f}s' for t in ts], 8, os.path.join(out_dir, f'{stem}-storyboard.jpg')):
        v['storyboard'] = f'{rel_dir}/{stem}-storyboard.jpg'
    # 前 3 秒钩子：0 / 0.5 / 1 / 1.5 / 2 / 2.5 秒
    hook_ts = [t for t in (0, 0.5, 1, 1.5, 2, 2.5) if t < d]
    if grid([frame(path, t, 240) for t in hook_ts], [f'{t:.1f}s' for t in hook_ts], 6, os.path.join(out_dir, f'{stem}-hook.jpg')):
        v['hookFrames'] = f'{rel_dir}/{stem}-hook.jpg'
    first = frame(path, min(0.5, d / 2), 320)
    if first:
        v['hash'] = image_info(first)['hash']
    if do_transcribe and has_audio:
        try:
            v['transcript'] = transcribe(path, whisper_model)
        except Exception as e:
            v['transcript'] = {'text': '', 'error': T('转写失败：{e}', e=str(e)[:120]), 'segments': []}
    return v


def fix_blank_thumb(a, video, mdir):
    """Facebook 给的视频封面有时是纯白/纯黑的第一帧，换成视频里 1.5 秒处的画面。"""
    p = os.path.join(mdir, f'{a["id"]}-thumb.jpg')
    try:
        if a.get('thumb') and 25 < ImageStat.Stat(Image.open(p).convert('L')).mean[0] < 235:
            return
        im = frame(video, min(1.5, (a.get('video') or {}).get('seconds', 3) / 2), THUMB_W)
        if im:
            im.save(p, quality=84)
            a['thumb'] = f'assets/media/{a["id"]}-thumb.jpg'
    except Exception:
        pass


def _images_for(a, root, mdir, proxy, full):
    """缩略图（视频封面 / 第一张图 / 卡片图）；full=True 时再下载图片广告的全部图片（最多 6 张）。"""
    aid = a['id']
    src = (a['videos'][0].get('poster') if a.get('videos') else None) or (a['images'][0] if a.get('images') else None) or         next((c['image'] for c in a.get('cards') or [] if c.get('image')), None)
    if src:
        raw = download(src, os.path.join(mdir, f'{aid}-src.jpg'), proxy, 40)
        info = save_thumb(raw, os.path.join(mdir, f'{aid}-thumb.jpg'))
        a['thumb'] = f'assets/media/{aid}-thumb.jpg'
        if not a.get('videos'):
            a['imageInfo'] = info
        os.remove(raw)
    if full:
        imgs = []
        for k, u in enumerate(a['images'][:6]):
            p = download(u, os.path.join(mdir, f'{aid}-img{k + 1}.jpg'), proxy, 40)
            imgs.append(f'assets/media/{aid}-img{k + 1}.jpg')
            if k == 0:
                a['imageInfo'] = image_info(Image.open(p))
        a['localImages'] = imgs


def localize(ads, root, settings, log, progress, check):
    """ads 已按爆款指数排好序。图片 8 线程并行下载；视频按顺序下载并拆解（ffmpeg / 转写比较吃 CPU）。返回 (视频数, 图片广告数, 失败数)。"""
    import concurrent.futures as cf
    proxy = settings.get('proxy') or ''
    max_v, max_i = settings.get('max_videos', 20), settings.get('max_images', 80)
    do_tr = settings.get('transcribe') and whisper_ok()
    mdir = os.path.join(root, 'assets', 'media')
    fails = 0
    full_ids = {a['id'] for a in [a for a in ads if not a.get('videos') and a.get('images')][:max_i]}
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(_images_for, a, root, mdir, proxy, a['id'] in full_ids): a for a in ads}
        avatars = {a['pageId']: a['pageAvatar'] for a in ads if a.get('pageAvatar') and a.get('pageId')}
        afuts = {ex.submit(download, u, os.path.join(root, 'assets', 'avatars', f'{pid}.jpg'), proxy, 20): pid for pid, u in avatars.items()}
        for i, f in enumerate(cf.as_completed(futs)):
            a = futs[f]
            progress(T('下载图片和封面 {i}/{n}', i=i + 1, n=len(ads)))
            try:
                f.result()
            except Exception as e:
                fails += 1
                a['mediaError'] = str(e).splitlines()[0][:160]
                log(T('图片下载失败 {id}：{e}', id=a['id'], e=a['mediaError']))
            if i % 10 == 0:
                check()
        ok_av = {afuts[f] for f in cf.as_completed(afuts) if not f.exception()}
    for a in ads:
        a['localAvatar'] = f'assets/avatars/{a["pageId"]}.jpg' if a.get('pageId') in ok_av else None
    n_i = sum(1 for a in ads if a.get('localImages'))
    n_v = 0
    for a in [a for a in ads if a.get('videos')][:max_v]:
        check()
        n_v += 1
        progress(T('处理视频 {i}/{n}（{p}）：下载、分镜、语音转写' if do_tr else '处理视频 {i}/{n}（{p}）：下载、分镜', i=n_v, n=min(max_v, sum(1 for x in ads if x.get('videos'))), p=a.get('pageName') or ''))
        try:
            v0 = a['videos'][0]
            p = download(v0.get('hd') or v0.get('sd'), os.path.join(mdir, f'{a["id"]}.mp4'), proxy, 120)
            a['localVideo'] = f'assets/media/{a["id"]}.mp4'
            a['video'] = process_video(p, mdir, 'assets/media', a['id'], do_tr, settings.get('whisper_model', 'small'))
            fix_blank_thumb(a, p, mdir)
        except Exception as e:
            fails += 1
            a['mediaError'] = str(e).splitlines()[0][:160]
            log(T('视频处理失败 {id}：{e}', id=a['id'], e=a['mediaError']))
    return n_v, n_i, fails
