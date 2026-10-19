"""一条命令完成安装和环境检查，全程不需要按键，方便 Claude Code / Codex 等 AI 助手代为安装。

用法（在项目文件夹里运行，用电脑上的 Python 3.10+）：
    python tools/setup.py               安装（创建 .venv、装依赖、装抓取用的浏览器、装语音转写），然后做环境检查
    python tools/setup.py --check       只做环境检查
    python tools/setup.py --no-whisper  不装视频语音转写（省约 100MB；首次转写还会下载约 500MB 模型）

最后一行输出 RESULT: OK / RESULT: WARN / RESULT: FAIL，退出码分别是 0 / 0 / 1。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = os.name == 'nt'
VPY = os.path.join(ROOT, '.venv', 'Scripts' if WIN else 'bin', 'python.exe' if WIN else 'python')
MIRROR = 'https://pypi.tuna.tsinghua.edu.cn/simple'


def say(msg):
    print(msg, flush=True)


def run(cmd):
    say('$ ' + ' '.join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def pip_install(req):
    pip = [VPY, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', req]
    if run(pip) == 0:
        return True
    say('默认源失败，改用清华镜像重试')
    return run(pip[:4] + ['-i', MIRROR] + pip[4:]) == 0


def install(whisper=True):
    if sys.version_info < (3, 10):
        say(f'[错误] Python 版本太低：{sys.version.split()[0]}，需要 3.10 或更高：https://www.python.org/downloads/')
        return False
    if not os.path.exists(VPY):
        say('[1/4] 创建独立的 Python 环境 .venv')
        if run([sys.executable, '-m', 'venv', '.venv']) != 0:
            say('[错误] 创建 .venv 失败')
            return False
    say('[2/4] 安装依赖')
    if not pip_install('requirements.txt'):
        say('[错误] 依赖安装失败：检查网络或代理（可以设置 HTTPS_PROXY 环境变量）后重试')
        return False
    say('[3/4] 安装抓取用的浏览器（Chromium）')
    if run([VPY, '-m', 'playwright', 'install', 'chromium']) != 0:
        say('[提示] 浏览器没装上；电脑里有 Google Chrome 或 Microsoft Edge 也能用')
    if whisper:
        say('[4/4] 安装视频语音转写（faster-whisper，可选）')
        if not pip_install('requirements-whisper.txt'):
            say('[提示] 语音转写没装上，不影响抓取和分析，只是视频没有口播文字')
    else:
        say('[4/4] 跳过语音转写')
    return True


def check():
    """用 .venv 里的 Python 调用面板自己的环境检查（和面板右上角“环境检查”一样）。"""
    if not os.path.exists(VPY):
        say('[错误] 还没有安装：先运行 python tools/setup.py')
        return 'FAIL'
    code = ('from app.util import _bundle_ok\n'
            'if not _bundle_ok():\n'
            '    print("  ✗ 程序文件：不完整或已被修改，面板无法启动，请重新下载原版")\n'
            '    print("RESULT: FAIL"); raise SystemExit\n'
            'from app.main import env_check\n'
            'r = env_check()\n'
            'for x in r: print(("  ✓ " if x["ok"] else "  ✗ ") + x["name"] + "：" + x["detail"])\n'
            'need = {"Python", "Playwright", "ffmpeg（视频分镜）"}\n'
            'hard = [x for x in r if not x["ok"] and x["name"] in need]\n'
            'soft = [x for x in r if not x["ok"] and x["name"] not in need]\n'
            'print("RESULT: " + ("FAIL" if hard else "WARN" if soft else "OK"))\n')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    say('环境检查：')
    out = subprocess.run([VPY, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    lines = ((out.stdout or '') + (out.stderr or '')).rstrip().splitlines()
    for line in lines[:-1] if lines and lines[-1].startswith('RESULT:') else lines:
        say(line)
    last = lines[-1] if lines else ''
    return last.split(':', 1)[1].strip() if last.startswith('RESULT:') else 'FAIL'


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    args = sys.argv[1:]
    if '--check' not in args and not install(whisper='--no-whisper' not in args):
        say('RESULT: FAIL')
        sys.exit(1)
    result = check()
    if result == 'OK':
        say('安装完成，可以启动面板了。')
    elif result == 'WARN':
        say('可以使用。上面打 ✗ 的项目不影响启动：访问 Facebook 失败要开代理/VPN；Claude Code 未登录只是没有 AI 分析；没有语音转写只是视频没有口播文字。')
    say('启动面板：Windows 双击 “2-启动面板.bat”；macOS 运行 mac-启动面板.command。面板地址 http://127.0.0.1:8766')
    say('RESULT: ' + result)
    sys.exit(1 if result == 'FAIL' else 0)


if __name__ == '__main__':
    main()
