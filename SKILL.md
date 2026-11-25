---
name: motion-templates
description: 用 MotionGit(.motion) 开源模板一键出知识讲解/口播视频。用户说"做条口播视频""知识讲解视频""用阿杜那套模板""酷炫科技风""用模板剪片"，或给出主题+文案想要 60fps 横屏知识视频时使用。自动选模板、自动装包、一条命令跑完 方案→预览→成片。
---

# MotionGit 模板剪辑（自动选模板 + 一条龙出片）

> **Owner**：知识讲解/口播类短视频的模板化生产
> **何时触发**：用户要"把这篇内容做成视频""做条口播/讲解视频""用阿杜的模板""酷炫科技风"
> **产出什么**：1920×1080 / 60fps / h264 无声片 + 混音成片 `silent-with-audio.mp4`，中间产物 `plan.json`、`preview.png`
> **禁止什么**：把 PDF/网页需求硬套进来（走 editorial-design / visual-deliver）；拿没有包的模板假装能出片；预览通过就宣布成片完成
> **怎样算验收**：用户看过 `preview.png`；`ffprobe` 确认分辨率/帧率/时长；最后一条命令的产物路径真实存在

## 一步到位（用户只需要说内容）

```bash
python D:/Claude/配置/.claude/skills/motion-templates/scripts/motion_tpl.py \
  build --template 385712 --brief <本期user.json> --out-dir <输出目录>
```

跑完给用户看 `preview.png`（此时还没成片），确认后再：

```bash
python .../motion_tpl.py render --template 385712 --out-dir <输出目录>
```

`build` 会自动：缺包就下载解压 → `npm ci` → plan → prepare → preview →（不加 `--skip-render` 时）render + 混音。
**默认加 `--skip-render`**，先给预览，避免用户还没确认就渲几百帧。

## 选模板（不让人挑 ID）

```bash
python .../motion_tpl.py pick --need "知识讲解 横屏" --top 5
```

打分规则：画幅是硬条件（不匹配 −20/-25），本地有包只 +6，扣不过画幅。所以别指望"有包就赢"。

| 内容类型 | 优先模板组 | 说明 |
| --- | --- | --- |
| 口播 + 观点/方法拆解 | `talk` 口播讲解（21 款） | 人是主角，画面辅助 |
| 纯讲解/科普/流程 | `explainer` 讲解（19 款） | 信息密度高，可无出镜 |
| 产品/功能展示 | `product` 产品展示（14 款） | 屏幕录制、作品墙 |
| 片头/标题/氛围 | `art` 艺术视觉（17 款） | 不承载长文案 |

## 当前能不能出片（2026-10-27 核实）

逐页复查 72 个官网（2026-10-27），下载分三档：

| 档位 | 数量 | 含义 | 能不能自动拿 |
| --- | --- | --- | --- |
| 开放 | 28 | 页面写 `Free signup. Free template download.` | **已全部下载入库**（2026-10-27，逐个验签通过） |
| 待达标 | 16 | 作品支持量达四项指标才开 | 等量，定期复查 |
| 关闭 | 28 | `下载开关保持关闭` | 暂不可得 |

- 本地 `library/` 现有 **28 个官网个人包 + 1 个 GitHub 公开包**，清单见 `data/downloaded.json`、`09 学习资料与数据库/.../已下载清单-28款.md`。
- 要新模板时先 `status` 看本地有没有；没有再去官网，开放档可直接用脚本拉（cookie 在 `mg_cookies.json`，过期重登）。
- 竖屏（1080×1920）本地只有 `583549` 和 `385712` 两款；要别的竖屏得等对应款开下载。
- 下载节奏：官网对密集请求会回 503，脚本按 15 秒间隔 + 退避重试跑，别开并发。

## 复查下载开关（有明确待办，别忘）

用户判断阿杜过两天会开放更多模板下载。**2026-10-29 之后**主动跑一次：

```bash
python .../scripts/check_downloads.py            # 逐款查，出状态表
python .../scripts/check_downloads.py --fetch    # 新开的全部抓进 library/
```

判读：页面有「下载开关保持关闭」= closed；有取包入口（`Free template download` / 登录链接）= open；都没有 = unknown，不猜。
注意 open 只代表门开着，官网取包要免费注册账号；免登录路径只存在于各仓库的 `downloads/` 目录。
抓完更新 `data/catalog.json` 快照、`09 学习资料与数据库/视频资料/20261027-阿杜Next-AI口播剪辑模板/模板库-72款索引导航.md` 的"已入库的包"。

## 两种包，两套入口（别混）

| | GitHub 公开包 | 官网个人包（登录下载） |
| --- | --- | --- |
| 例 | `kinetic-tech-zh.motion` 0.2.7-open-beta | `MotionGit-385712-v0.2.40-alpha.1.motion` |
| 结构 | `adapter.py` + `core/` 工程 | `assistant/motion.mjs` + `content/release.bin` |
| 入口 | `uv run adapter.py plan/prepare/preview/render`（本 skill 的 `motion_tpl.py build` 封装的就是这套） | `node assistant/motion.mjs start <原始.motion> --summary`，按返回的 `productionEntry` 读 schema 继续 |
| 额外能力 | 无 | 个人 key、免费素材 API（Pexels/Pixabay/Unsplash 图、视频、贴纸、音乐、TTS），每账号每日 30 次免费 |
| 安全 | 无凭证 | **`personal/motiongit.key.json` 是个人标识，禁止外传、禁止进任何对外产物**；解包只取 `assistant/` 与说明文件，`content/`、`personal/` 留在原包里 |

正式出片优先用个人包（版本新、支持竖屏、带素材库）；公开包是本机无账号时的兜底。

## 本期输入的写法（user.json）

字段来自包内 `params.schema.json`，镜头组来自 `CREATION.md`：

| 组 | 必填 basic | 基础时长 | 用途 |
| --- | --- | --- | --- |
| B1 | `keyword` `explanation` | 8s | 讲一个关键词 |
| B2 | `heading` `points`(1–5) | 10s | 讲 1–5 个点 |
| B3 | `heading` `left` `right` `conclusion` | 10s | 两个角度对比下结论 |
| B4 | `summary` `action` | 8s | 总结 + 行动 |

每组建后可延长 0–12 秒阅读停留；原生动作不变速。用户没给人物/配音/配乐时不追问，`media.*.mode` 写 `none`，`soundEffects` 写 `native`。

模板要求：按语义选组，别把没做完的事画成完成章，保留否定、条件、数字和结论。改写意思要给用户核对。

## 边界（跟其他 skill 别打架）

- **本 skill**：有现成 .motion 包 + 要规范的知识讲解片，速度优先。
- **video-shotcraft**：电影感产品片、2.5D 运镜、卡点剪辑。
- **huashu-design**：文字驱动的 HTML 动画 → MP4/GIF，无模板依赖。
- **PDF / 网页**：本 skill 不产出。要按某个模板的视觉语言做 PDF/网页，把模板 demo 当风格参考，交给 `editorial-design` 或 `visual-deliver`。

## 包内安全审查（2026-10-27 已做）

`motion.json` 声明 `permissions.network: false`；脚本只起本地 http 服务给 headless Chrome 取静态文件，子进程只调 `ffmpeg`/`ffprobe`；无外网请求、无凭证读取、无路径删除。包体 SHA256 与官方 `SHA256SUMS` 一致。

## 本机实测记录

- 2026-10-27：Windows 11 + Node 24.20 + Python 3.13 + uv 0.12.13 + FFmpeg 8.1，`B1` 8 秒 480 帧渲染通过。`silent.mp4` 1920×1080/60fps/h264，`errors: []`。
- 官方 README 只声明 macOS 横屏已测、Windows 未验证 —— 上面这条是我方新增证据，不是官方结论。
