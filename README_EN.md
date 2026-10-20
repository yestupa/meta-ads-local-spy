# Meta Ad Spy Panel · for cross-border e-commerce

> Type a product keyword or a brand name and pull the ads currently running on Facebook / Instagram from the Meta Ad Library,
> save the creatives locally, and get a breakdown of the **images, copy and videos**. Free, runs on your own PC,
> no Meta API needed. AI analysis can use your own Claude subscription through Claude Code, so no API key is needed.

[中文说明](README.md) · Author: 图帕先生 / yestupa ([yestupa.com](https://yestupa.com))

## 🚀 Install with AI (recommended)

If you have [Claude Code](https://claude.com/claude-code) or Codex, just tell it:

```
Install and start this tool for me: https://github.com/yestupa/meta-ads-local-spy
```

It will clone the repo, check Python, install dependencies and the browser, and start the panel.
To update later, ask it to "update meta-ads-local-spy". Prefer a download? Get the zip from
[Releases](https://github.com/yestupa/meta-ads-local-spy/releases).

![Brand mode](docs/screenshots/01-brand-summary.png)

> The panel has an **English / 中文** switch at the top right. It opens in your browser's language the first time;
> AI analysis, progress messages and exports for a new job use the language selected when the job was started.

## What it does

- **Keyword mode**: `posture corrector` → who is advertising in this niche, how long their ads have been running,
  which angles and offers they use, and what the landing products sell for.
- **Brand mode**: `chewy` or `chewy.com` → finds the brand's official Facebook page and collects only that page's ads.
- **Winner score (0–100)**: an estimate from public Ad Library fields (days running, number of ads sharing the creative,
  position in the impressions-sorted list, platforms). Meta does not publish spend or likes for non-EU commercial ads.
- **Video**: duration, aspect ratio, cut points and average shot length, first-3-second frames, per-second storyboard,
  timestamped transcript (local Whisper model; click a line to jump to that second).
- **Images**: dominant colors, aspect ratio, tone, and the same image reused by several advertisers.
- **Copy**: tags (discount, free shipping, BOGO, urgency, social proof, guarantee, pain point, authority, before/after,
  holiday, price anchor), opening-line type, length, frequent phrases counted per advertiser.
- **Stores & products**: advertiser ranking; for Shopify product pages, the product title, price, compare-at price and
  launch date; "same product, several stores" detection.
- **AI (Claude)**: a review of every ad's copy, deep breakdowns of the top creatives (OCR, visual, shot-by-shot script,
  strengths, improvements, rewrite), a market or brand summary, and 3 ready-to-shoot ad concepts.
- Favorites across jobs, offline HTML report export, and CSV export.

## Manual install

1. Install **Python 3.10+** (Windows: tick *Add python.exe to PATH*). You need a network that can reach facebook.com.
2. Install: Windows → double-click `1-安装.bat`; macOS → run `mac-安装.command`; or run `python tools/setup.py`.
3. Start: Windows → double-click `2-启动面板.bat`; macOS → run `mac-启动面板.command`. The panel opens at http://127.0.0.1:8766.
4. Optional AI: install [Claude Code](https://claude.com/claude-code) and log in (`claude` → `/login`), or paste a Claude API key in Settings.

## Limits

Without a Facebook login, the Ad Library returns only 30 ads per page load and pagination is rate-limited. The tool runs several
sort / format / platform combinations (and in brand mode, in-page keyword searches) and merges the results, giving roughly
60–300 ads per keyword or 100–900 per brand depending on depth. It does not retrieve every ad of a large advertiser.

## License

Source-available, free to use and share, keep the author credits, no paid redistribution. See [LICENSE](LICENSE).

## Author

Made by 图帕先生 (yestupa)

- WeChat: yestupasemseo
- Web: [yestupa.com](https://yestupa.com) · [yestupa.net](https://yestupa.net)
- Feedback and suggestions: [success@yestupa.com](mailto:success@yestupa.com)

If you find it useful, a ⭐ Star helps. Issues and feature requests are welcome.
