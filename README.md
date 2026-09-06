# 语音约碰面地点

本地全栈项目：按住录音，为同一座城市里的两个人推荐中间附近的店。

当前进度：项目骨架。已实现后端 `GET /health` 和可打开的前端基础页。录音与其他业务接口尚未开发。

## 环境

- Python 3.11
- Node.js 22.12 及以上的 22.x
- 后端端口 `8003`
- 前端端口 `5175`

## 安装依赖

后端（在 `backend/` 目录）：

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` 中的密钥可先留空。健康检查不调用外部服务。

前端（在 `frontend/` 目录）：

```bash
cd frontend
npm install
```

## 启动

后端：

```bash
cd backend
source .venv/bin/activate
python main.py
```

前端：

```bash
cd frontend
npm run dev
```

## 本轮如何验证

1. 浏览器打开 `http://localhost:8003/health`，应返回 HTTP 200，JSON 含 `request_id` 和 `data.status` 为 `ok`。
2. 浏览器打开 `http://localhost:8003/docs`，展开 `GET /health` 并 Execute，结果同上。
3. 浏览器打开 `http://localhost:5175`，应看到基础页。可点击「检查后端健康状态」确认前端能访问后端（同时验证 CORS）。

## 测试说明

- 模拟测试：后续业务接口会用 Mock，避免反复调用付费服务。本轮仅有健康检查，可用 `cd backend && pytest`。
- 真实接口验收：配置密钥后，由你确认再测 ASR、DeepSeek、高德、TTS 和前端全链路。Mock 通过不能证明真实项目已跑通。

本轮的安装、启动和测试由开发者本地执行。
