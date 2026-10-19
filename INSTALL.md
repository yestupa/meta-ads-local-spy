# 安装说明（写给 AI 编程助手：Claude Code、Codex 等）

用户让你“安装 / 启动 / 更新”这个工具时，按下面的步骤做。每一步都用一两句大白话告诉用户你在做什么：用户大多不是程序员。

仓库地址：https://github.com/yestupa/meta-ads-local-spy

## 1. 放在哪里

- 用户指定了位置就用用户的；没指定就用用户主目录下的 `meta-ads-local-spy`
  （Windows：`%USERPROFILE%\meta-ads-local-spy`，macOS：`~/meta-ads-local-spy`）。
- 这个文件夹已经存在并且是 git 仓库：说明之前装过，按第 7 步“更新”处理，不要删除重装（`data/` 里有用户的设置和抓取结果）。

## 2. 下载代码

```bash
git clone https://github.com/yestupa/meta-ads-local-spy.git
```

- 没有 git，或者 GitHub 连不上：下载 https://github.com/yestupa/meta-ads-local-spy/archive/refs/heads/main.zip ，解压后把文件夹改名为 `meta-ads-local-spy`。
- 还是连不上：请用户打开代理/VPN，并问清代理端口（常见 7890），然后设置环境变量 `HTTPS_PROXY` 和 `HTTP_PROXY` 为 `http://127.0.0.1:<端口>` 再试。不要自己猜端口。
- 如果你运行在不能联网的沙箱里，先向用户申请联网权限。

## 3. 检查 Python

需要 Python 3.10 或更高版本。Windows 先试 `py -3 --version`，再试 `python --version`；macOS 用 `python3 --version`。

没有或版本太低：请用户从 https://www.python.org/downloads/ 安装（Windows 安装时勾选 **Add python.exe to PATH**），装好后重新打开终端。用 winget、brew 等命令代装之前，先征得用户同意。

## 4. 安装依赖

在项目文件夹里运行（Windows 用 `py -3`，macOS 用 `python3`）：

```bash
python tools/setup.py
```

- 全程不需要按键，第一次大约 3 到 10 分钟，给足超时时间（建议 15 分钟）。
- 它会创建 `.venv`、安装依赖（默认源失败会自动换清华镜像）、安装抓取用的 Chromium、安装视频语音转写（faster-whisper），最后做环境检查。
- 用户不需要视频口播文字、或者磁盘/网络紧张：加 `--no-whisper`，跳过语音转写。
- 看最后一行：`RESULT: OK` 全部正常；`RESULT: WARN` 能用，但有 ✗ 项要告诉用户；`RESULT: FAIL` 不能用，按输出处理后重新运行。
- 只想重新检查环境：`python tools/setup.py --check`。

## 5. 处理检查结果里的 ✗

| 项目 | 怎么处理 |
|---|---|
| 访问 Facebook | 请用户打开代理/VPN（要能打开 facebook.com）；也可以启动面板后在“设置”里填写代理地址。不需要把节点切到目标国家，国家在面板里选 |
| ffmpeg（视频分镜） | 重新运行 `python tools/setup.py`（ffmpeg 随 imageio-ffmpeg 一起安装） |
| 语音转写 | 不影响抓取。需要的话重新运行 `python tools/setup.py`；首次转写会自动下载约 500MB 模型 |
| AI 分析：Claude Code | 不影响抓取和本地统计。要用 AI 分析，请用户自己在终端里运行 `claude`，再输入 `/login` 登录。国内网络先设置代理，否则会报 `OAuth error 403`。登录授权码只能由用户自己粘贴到终端，你不要代为输入 |
| 程序文件不完整 | 程序文件被改动过。不要尝试修复或绕过，请用户重新下载原版仓库 |

## 6. 启动面板

面板是一个要一直运行的本地服务，**不要在你自己的会话里前台运行**（会卡住你的会话，你的会话结束后面板也会停）。用单独的窗口启动：

- Windows：`cmd /c start "" "2-启动面板.bat"`
- macOS：`open mac-启动面板.command`

浏览器会自动打开 http://127.0.0.1:8766 。告诉用户：
- 使用期间不要关闭那个黑色命令行窗口，关掉面板就停了；
- 以后自己启动：Windows 双击 `2-启动面板.bat`，macOS 双击 `mac-启动面板.command`；
- 用户只说“安装”时，也照这一步把面板启动起来，让用户马上能用。
- 想在桌面放启动快捷方式的话，先问用户，用户同意再创建，不要擅自创建。
- 第一次使用先点右上角“环境检查”，然后在左侧选“关键词模式”（输入产品词，例如 posture corrector）或“品牌模式”（输入品牌名或官网域名，例如 chewy.com），点“开始抓取”。详细用法见 README.md。

## 7. 更新

```bash
git pull
python tools/setup.py
```

不要删除或覆盖 `data/` 文件夹。如果是用 zip 装的（没有 `.git`），下载新的 zip 解压，只把除 `data/` 和 `.venv/` 以外的文件覆盖过去，再运行 `python tools/setup.py`。

## 8. 不要做的事

- 遵守 CLAUDE.md / AGENTS.md 里的规则。
- 不要把 `data/`（里面有用户的设置、API key 和抓取结果）上传、提交或发给任何人。
- 不要代用户输入密码、API key 或登录授权码。
- 不要替用户登录 Facebook。本工具不需要登录，只读取广告资料库公开展示的内容。
