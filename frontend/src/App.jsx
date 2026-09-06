import { useEffect, useState } from "react";
import { getHealth } from "./api.js";
import RecordButton from "./components/RecordButton.jsx";
import RecordingPreview from "./components/RecordingPreview.jsx";

export default function App() {
  const [city, setCity] = useState("杭州");
  const [healthMessage, setHealthMessage] = useState("尚未检查后端。");
  const [healthBusy, setHealthBusy] = useState(false);
  const [recordError, setRecordError] = useState("");
  const [recording, setRecording] = useState(null);

  useEffect(() => {
    return () => {
      if (recording?.url) {
        URL.revokeObjectURL(recording.url);
      }
    };
  }, [recording]);

  async function checkHealth() {
    setHealthBusy(true);
    setHealthMessage("正在检查后端…");
    try {
      const { data } = await getHealth();
      setHealthMessage(
        `健康检查成功。status=${data.data.status}，request_id=${data.request_id}`,
      );
    } catch (error) {
      const detail = error.response
        ? `HTTP ${error.response.status}`
        : error.message;
      setHealthMessage(`健康检查失败：${detail}。请确认后端已在 8003 端口启动。`);
    } finally {
      setHealthBusy(false);
    }
  }

  function handleRecordingReady({ blob, durationMs, mimeType }) {
    setRecording((current) => {
      if (current?.url) {
        URL.revokeObjectURL(current.url);
      }
      return {
        blob,
        durationMs,
        mimeType,
        url: URL.createObjectURL(blob),
      };
    });
    setRecordError("");
  }

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>按住按钮录音。本轮只做本地录音，不上传、不识别、不找店。</p>

      <label className="city-field">
        城市
        <input
          value={city}
          onChange={(event) => setCity(event.target.value)}
          autoComplete="off"
        />
      </label>

      <RecordButton
        onRecordingReady={handleRecordingReady}
        onError={setRecordError}
      />
      {recordError ? <p className="status error">{recordError}</p> : null}

      <RecordingPreview recording={recording} />

      <section className="health">
        <p>后端地址：http://localhost:8003</p>
        <button type="button" onClick={checkHealth} disabled={healthBusy}>
          {healthBusy ? "检查中…" : "检查后端健康状态"}
        </button>
        <p className="status">{healthMessage}</p>
      </section>
    </main>
  );
}
