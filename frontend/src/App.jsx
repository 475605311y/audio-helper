import { useState } from "react";
import { getHealth } from "./api.js";

export default function App() {
  const [message, setMessage] = useState("尚未检查后端。");
  const [busy, setBusy] = useState(false);

  async function checkHealth() {
    setBusy(true);
    setMessage("正在检查后端…");
    try {
      const { data } = await getHealth();
      setMessage(
        `健康检查成功。status=${data.data.status}，request_id=${data.request_id}`,
      );
    } catch (error) {
      const detail = error.response
        ? `HTTP ${error.response.status}`
        : error.message;
      setMessage(`健康检查失败：${detail}。请确认后端已在 8003 端口启动。`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>第一版骨架页。录音和其他业务接口尚未接入。</p>
      <p>后端地址：http://localhost:8003</p>
      <button type="button" onClick={checkHealth} disabled={busy}>
        {busy ? "检查中…" : "检查后端健康状态"}
      </button>
      <p className="status">{message}</p>
    </main>
  );
}
