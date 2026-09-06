# 语音约碰面地点

本地全栈项目：按住录音，为同一座城市里的两个人推荐中间附近的店。

链路：录音 → `/upload` → `/asr` → `/extract` → `/search` → `/finalize` → 播放 `/audio/{id}`。

当前不要把本仓库当成已验收完成。接口和页面已按第一条提示词接好，仍有一条启动清理未实现；真实联调和多项异常尚未由开发者逐项签字。

## 当前状态

已实现（代码已写，不等于验收通过）：

- 后端 FastAPI：`GET /health`、`POST /upload`、`POST /asr`、`POST /extract`、`POST /search`、`POST /finalize`、`GET /audio/{audio_id}`
- 统一成功结构 `{ request_id, data }`；音频下载成功返回文件，失败返回统一 JSON 错误
- 前端 React + Vite + JavaScript，Axios 封装在 `frontend/src/api.js`
- 按住录音（WebM/Opus、1–60 秒、5MB），城市默认杭州可改
- 按阶段显示上传中 / 识别中 / 提取中 / 找店中 / 生成推荐中
- 失败时停止后续请求并保留本轮已完成信息；重新录音清空上一轮并忽略迟到响应
- `audio_id` / `search_id` / 播报 `audio_id` 读取时检查 24 小时有效期
- 后端 Mock 测试覆盖各接口正常与异常分支（以你本地 `pytest` 结果为准）

尚未实现：

- 启动时清理超过 24 小时的临时数据。约定要求启动清理与读取过期检查同时存在，清理不能代替读取检查。目前只有读取时检查。

尚未验证（有代码或有过零星联调，但不能标通过）：

- 麦克风拒绝、非法文件、重复操作
- 地址缺失、人数不符、跨城、定位不明确、无候选的页面表现
- 外部服务超时 / 502，以及 TTS 或音频下载失败后的文字降级
- 新旧请求不混用、组件卸载释放资源
- `search_id` / 播报音频编号过期的专用 Mock；真实 24 小时过期
- 全链路语音播报是否稳定可听（曾出现 `finalize` 502）

## 环境

约定：

- Python 3.11
- Node.js 22.12 及以上的 22.x
- 后端 `http://localhost:8003`
- 前端 `http://localhost:5175`
- CORS 仅放行 `http://localhost:5175` 和 `http://127.0.0.1:5175`

本机若没有 `python3.11`，可用当前的 `python3` 建虚拟环境，但与约定版本不一致，验收时写明实际版本。

另外需要本机 **`ffprobe`（FFmpeg）**，供 `/upload` 探测真实容器、编码和时长。这是探测，不是转码。浏览器 WebM 常缺少 Duration，会再读 packet 时间戳。没有 `ffprobe` 时，真实上传会失败。

```bash
ffprobe -version
```

macOS 可用 Homebrew `brew install ffmpeg`，或从 evermeet 等渠道把 `ffprobe` 放到 PATH。

## 配置

```bash
cd backend
cp .env.example .env
```

在 `backend/.env` 填写真实密钥，不要提交该文件：

- `BAILIAN_API_KEY`：百炼，北京地域，ASR / TTS
- `DEEPSEEK_API_KEY`：提取与推荐语
- `AMAP_API_KEY`：高德 Web 服务 Key

模型与地址已在 `.env.example` 分开配置，不要用同一套规则拼接全部供应商地址。密钥留空时，`GET /health` 仍应成功；业务接口会返回 502「服务暂不可用」，这是预期，不是健康检查失败。

## 目录

```text
project/
├── backend/
│   ├── main.py
│   ├── api/
│   ├── services/
│   ├── prompts/          extract.txt、finalize.txt
│   ├── schemas.py
│   ├── config.py
│   ├── errors.py
│   ├── storage/          audio、search、tts
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── recording.js
│   │   └── components/
│   └── package.json
├── .gitignore
└── README.md
```

临时文件、密钥、虚拟环境和 `node_modules` 不入库。`.gitignore` 已忽略 `.env`、`.venv/`、`backend/storage/{audio,search,tts}/*`（保留 `.gitkeep`）、`node_modules/`、常见音频扩展名。

编号：录音 `rec_`，查询 `srch_`，播报 `tts_`。都不是服务器路径。`/finalize` 只带 `search_id`，不由前端重新拼装店铺。

## 安装

后端：

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

前端：

```bash
cd frontend
npm install
```

## 启动

两个终端分别启动。

```bash
cd backend
source .venv/bin/activate
python3 main.py
```

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5175`。后端文档：`http://localhost:8003/docs`。根路径 `GET /` 为 404 是预期。

## 测试说明

Mock 通过不能替代真实接口联调。下面两类结果请分开记录。

### 模拟测试（不打付费接口）

在已激活的后端虚拟环境中：

```bash
cd backend
source .venv/bin/activate
pytest
```

覆盖健康检查、上传校验、过期 `audio_id`、空识别、提取业务错误、搜店排序与模糊定位、推荐语失败、TTS 降级等。不证明百炼 / DeepSeek / 高德真实可用。

用 `/docs` 也可单独测后端，但上传真实录音需要 `ffprobe`；`/asr` 及之后会消耗配额。

### 真实接口验收（需密钥，由你执行）

1. `.env` 已填三把钥匙，重启后端使配置生效。
2. 确认 `ffprobe` 可用。
3. 打开前端，先看健康检查 `data.status=ok`。
4. 按下面「验收清单」逐项做。正常路径必须用真实录音走完整链，不能只用 Mock。
5. 业务错误可用口述触发（例如只说一个人的位置、两座城市、我家/公司）。
6. 外部 502/504、TTS 降级可用 Mock 先看结构，再用真实故障或偶发失败对照页面。

前端超时略长于后端预算，不自动重试付费接口：

| 接口 | 后端预算约 | 前端超时 |
|---|---|---|
| `/health` | — | 3s |
| `/upload` | 探测约 5s | 12s |
| `/asr` | 18s | 25s |
| `/extract` | 12s | 20s |
| `/search` | 12s（双方定位 + 2000/5000 米） | 18s |
| `/finalize` | 25s（推荐语 10s + TTS 10s + 下载 4s） | 32s |
| `/audio/{id}` | — | 8s |

## 验收清单

按操作顺序做。每项记下：通过 / 失败 / 未做，以及真实服务还是 Mock。不要把未做的项标成通过。

### 1. 正常录音到推荐结果和语音播放

需要真实服务。

1. 打开 `http://localhost:5175`，城市保持「杭州」。
2. 页底健康检查为 `status=ok`，或 Network 中 `GET /health` 为 200。
3. 开发者工具打开 Network，过滤框留空，点 Fetch/XHR，勾选 Preserve log，再录音。
4. 按住说：「我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。」松手，时长 1–60 秒。
5. 状态依次为：上传中、识别中、提取中、找店中、生成推荐中。
6. 页面出现识别文字、两地与类别、最多 3 家店（店名、地址、距离中点的米数，顺序与接口一致，不是示例店）。
7. 出现推荐语；若自动播放被拦截，点「播放推荐语音」。
8. Network 顺序：`POST /upload` → `/asr` → `/extract` → `/search` → `/finalize` → `GET /audio/tts_...`。最后一条必须是 `tts_`，不要用上传的 `rec_` 拼播放地址。
9. 距离文案只说「距离中点」，不宣称两人出行时间相同。

### 2. 麦克风拒绝、非法文件和重复点击

| 项 | 怎么做 | 预期 | 验证方式 |
|---|---|---|---|
| 2.1 麦克风拒绝 | 浏览器拒绝麦克风后按住说话 | 中文提示，Network 无 `/upload` | 真实浏览器 |
| 2.2 录制失败 / 过短 | 按住不足 1 秒松开 | 提示 1–60 秒，不上传 | 真实浏览器 |
| 2.3 过长 | 按住到 60 秒自动停止 | 得到文件并可继续；再长的前端会截断 | 真实浏览器 |
| 2.4 非法格式 | `/docs` 上传 txt/mp3 等非约定格式 | 415，统一错误 JSON，`stage=upload` | `/docs` 或 Mock `pytest` |
| 2.5 文件过大 | `/docs` 上传超过 5MB | 413 | `/docs` 或 Mock |
| 2.6 时长不合规 | `/docs` 上传时长不在 1–60 秒的合法容器 | 422 | `/docs` 或 Mock |
| 2.7 处理中再录音 | 一轮进行中再录并提交 | 旧请求取消或迟到响应被忽略；页面只显示新一轮 | 真实前端 |
| 2.8 不重试付费接口 | 观察失败后的 Network | 每个付费步骤只出现一次，无自动重打 | 真实或断网 |

前端没有本地选文件上传，非法文件走 `/docs` 测后端。

### 3. 地址缺失、人数不符、跨城、定位不明确、无候选

先可用 Mock 看状态码和 `error.code`；页面文案必须再各录一句真实语音。缺信息时不得出现搜店结果。

| 项 | 口述或请求示例 | 预期 | 验证方式 |
|---|---|---|---|
| 3.1 地址缺失 | 「我和朋友想找个咖啡店碰面。」 | `/extract` 422，`INCOMPLETE_INFO`，不请求 `/search` | 真实口述；结构可用 Mock |
| 3.2 含糊地址 | 「我在我家，朋友在公司，找咖啡店。」 | 422，不搜店 | 真实口述 |
| 3.3 人数不符 | 三个人、三个地点 | `/extract` 422，`PARTY_COUNT_INVALID` | 真实口述；结构可用 Mock |
| 3.4 跨城 | 「我在杭州东站，朋友在北京西站，找咖啡店。」 | 422 `CROSS_CITY`，不搜店或 search 同样拒绝 | 真实口述 |
| 3.5 定位不明确 | 过于宽泛或一对多名 | `/search` 422，提示说得更具体 | 真实地点；规则可用 Mock |
| 3.6 无候选 | 偏僻中点或冷门类别 | `/search` 422，先 2000 米再 5000 米仍空 | 真实或 Mock |
| 3.7 识别为空 | 几乎无语音的有效文件（若能造出） | `/asr` 422 | 真实较难；优先 Mock |

### 4. 外部服务异常、超时、TTS / 音频降级

| 项 | 预期 | 验证方式 |
|---|---|---|
| 4.1 钥匙为空 | 对应步骤 502「服务暂不可用」 | 可临时清空钥匙后重启（测完改回） |
| 4.2 供应商 5xx / 网络错误 | 502，`error.stage` 为当前步骤 | Mock 已覆盖；真实以偶发或断网对照 |
| 4.3 供应商超时 | 504，中文超时提示 | Mock；真实较难稳定复现 |
| 4.4 模型 JSON 非法 | `/extract` 或 `/finalize` 502，不当成用户没说清 | Mock |
| 4.5 推荐语失败 | `/finalize` 502 或 504，页面保留店铺，不出现空推荐语成功 | 真实曾出现 502；结构以 Mock 为准 |
| 4.6 TTS 或供应商音频下载失败 | `/finalize` 仍 200，有 `reply_text`，`audio_url` 为 `null`，`warning` 为中文；页面保留文字 | Mock 已覆盖；真实需供应商 TTS 失败 |
| 4.7 播放地址加载失败 | 保留推荐语，提示语音播放失败 | 真实（断网或无效 `tts_`） |
| 4.8 自动播放被拦截 | 出现「播放推荐语音」按钮，点击可听 | 真实浏览器 |

### 5. 失败保留、重录清除、新旧不混用

需要真实前端。

1. 让一轮停在 `/extract` 或 `/finalize` 失败：识别文字和已完成的提取 / 店铺应还在。
2. 再录一句完全不同的内容并提交：旧编号、旧文字、旧店铺、旧推荐语和旧音频应清空，旧音频停止。
3. 第一轮尚未结束时开始第二轮：页面不得把第一轮迟到的店铺或推荐语写进第二轮。
4. 离开页面后再回来：麦克风指示灯应灭，不应继续占用来源。

### 6. 编号有效期、临时数据、密钥和 Git

| 项 | 预期 | 验证方式 |
|---|---|---|
| 6.1 读取过期 `audio_id` | `/asr` 404，统一错误 | Mock 已有；真实需改元数据时间或等 24 小时 |
| 6.2 不存在的 `search_id` | `/finalize` 404 | Mock 或 `/docs` |
| 6.3 用 `rec_` 请求 `/audio/{id}` | 404 JSON，不把上传录音当播报 | Mock |
| 6.4 启动清理超过 24 小时的文件 | 启动后过期文件从 `storage/` 删除，但读取仍要自己做 TTL 检查 | **尚未实现，本项不能验收为通过** |
| 6.5 `.env` 不在 Git | `git status` / `git ls-files` 无 `.env`、无真实钥匙 | 本地 Git 检查，不要把钥匙贴进聊天 |
| 6.6 运行数据不入库 | `storage/audio|search|tts` 下的录音和 JSON 被忽略 | `git status` |
| 6.7 `.env.example` 只有空值或安全占位 | 可入库 | 打开文件目视 |

## 日志与安全

日志记录阶段和错误类型，不打印密钥或音频 Base64。各接口耗时尚未做成统一字段，验收时不要当成已具备的可观察项。
