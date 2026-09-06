import { useEffect, useRef, useState } from "react";
import {
  downloadAudio,
  extractMeetup,
  finalizeMeetup,
  getHealth,
  isCanceled,
  readApiError,
  recognizeAudio,
  searchMeetup,
  uploadAudio,
} from "./api.js";
import RecordButton from "./components/RecordButton.jsx";
import RecordingPreview from "./components/RecordingPreview.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import StatusBar from "./components/StatusBar.jsx";
import { extensionForMime } from "./recording.js";

const STAGE_LABELS = {
  health: "检查服务",
  upload: "上传中",
  asr: "识别中",
  extract: "提取中",
  search: "找店中",
  finalize: "生成推荐中",
  done: "已完成",
};

export default function App() {
  const [city, setCity] = useState("杭州");
  const [healthMessage, setHealthMessage] = useState("尚未检查后端。");
  const [healthOk, setHealthOk] = useState(false);
  const [recordError, setRecordError] = useState("");
  const [recording, setRecording] = useState(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [extract, setExtract] = useState(null);
  const [pois, setPois] = useState([]);
  const [replyText, setReplyText] = useState("");
  const [warning, setWarning] = useState("");
  const [showPlayButton, setShowPlayButton] = useState(false);

  const cityRef = useRef(city);
  const taskSeqRef = useRef(0);
  const abortRef = useRef(null);
  const playbackRef = useRef(null);
  const playbackUrlRef = useRef(null);
  const recordingRef = useRef(null);

  cityRef.current = city;

  useEffect(() => {
    checkHealth();
    return () => {
      abortRef.current?.abort();
      stopPlayback();
      if (recordingRef.current?.url) {
        URL.revokeObjectURL(recordingRef.current.url);
      }
    };
  }, []);

  function stopPlayback() {
    if (playbackRef.current) {
      playbackRef.current.pause();
      playbackRef.current.src = "";
      playbackRef.current = null;
    }
    if (playbackUrlRef.current) {
      URL.revokeObjectURL(playbackUrlRef.current);
      playbackUrlRef.current = null;
    }
    setShowPlayButton(false);
  }

  function clearRoundResults() {
    setTranscript("");
    setExtract(null);
    setPois([]);
    setReplyText("");
    setWarning("");
    stopPlayback();
  }

  async function checkHealth() {
    setHealthMessage("正在检查后端…");
    try {
      const response = await getHealth();
      const status = response.data.data.status;
      setHealthOk(status === "ok");
      setHealthMessage(`健康检查成功。status=${status}，request_id=${response.data.request_id}`);
    } catch (error) {
      setHealthOk(false);
      setHealthMessage(`健康检查失败：${readApiError(error)}`);
    }
  }

  function handleRecordingReady({ blob, durationMs, mimeType }) {
    setRecording((current) => {
      if (current?.url) {
        URL.revokeObjectURL(current.url);
      }
      const next = {
        blob,
        durationMs,
        mimeType,
        url: URL.createObjectURL(blob),
      };
      recordingRef.current = next;
      return next;
    });
    setRecordError("");
    startPipeline(blob, mimeType);
  }

  function handleRecordError(message) {
    setRecordError(message);
  }

  async function startPipeline(blob, mimeType) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const taskSeq = taskSeqRef.current + 1;
    taskSeqRef.current = taskSeq;

    clearRoundResults();
    setStatusError(false);
    setStatusMessage("");

    const selectedCity = cityRef.current.trim();
    if (!selectedCity) {
      setBusy(false);
      setStatusError(true);
      setStage("");
      setStatusMessage("请先填写城市。");
      return;
    }

    setBusy(true);

    const signal = controller.signal;
    const stillCurrent = () => taskSeqRef.current === taskSeq && !signal.aborted;

    try {
      setStage("upload");
      const file = new File(
        [blob],
        `meetup-recording.${extensionForMime(mimeType)}`,
        { type: blob.type || mimeType },
      );
      const uploadResponse = await uploadAudio(file, { signal });
      if (!stillCurrent()) {
        return;
      }
      const audioId = uploadResponse.data.data.audio_id;

      setStage("asr");
      const asrResponse = await recognizeAudio(audioId, { signal });
      if (!stillCurrent()) {
        return;
      }
      const text = asrResponse.data.data.text;
      setTranscript(text);

      setStage("extract");
      const extractResponse = await extractMeetup(text, selectedCity, { signal });
      if (!stillCurrent()) {
        return;
      }
      const extractData = extractResponse.data.data;
      setExtract(extractData);

      setStage("search");
      const searchResponse = await searchMeetup(
        {
          city_a: extractData.city_a,
          address_a: extractData.address_a,
          city_b: extractData.city_b,
          address_b: extractData.address_b,
          category: extractData.category,
        },
        { signal },
      );
      if (!stillCurrent()) {
        return;
      }
      const searchData = searchResponse.data.data;
      setPois(searchData.pois || []);

      setStage("finalize");
      const finalizeResponse = await finalizeMeetup(searchData.search_id, { signal });
      if (!stillCurrent()) {
        return;
      }
      const finalizeData = finalizeResponse.data.data;
      setReplyText(finalizeData.reply_text);
      setWarning(finalizeData.warning || "");

      if (finalizeData.audio_url) {
        await playRemoteAudio(finalizeData.audio_url, signal, stillCurrent);
      }

      if (stillCurrent()) {
        setStage("done");
        setStatusMessage("本轮已完成。");
      }
    } catch (error) {
      if (!stillCurrent() || isCanceled(error)) {
        return;
      }
      setStatusError(true);
      setStatusMessage(readApiError(error));
    } finally {
      if (stillCurrent()) {
        setBusy(false);
      }
    }
  }

  async function playRemoteAudio(audioUrl, signal, stillCurrent) {
    try {
      const response = await downloadAudio(audioUrl, { signal });
      if (stillCurrent && !stillCurrent()) {
        return;
      }
      const blob = response.data;
      if (blob.type && blob.type.includes("application/json")) {
        setWarning((current) => current || "推荐语已生成，但语音播放失败，请阅读文字结果。");
        return;
      }
      if (playbackUrlRef.current) {
        URL.revokeObjectURL(playbackUrlRef.current);
      }
      const objectUrl = URL.createObjectURL(blob);
      playbackUrlRef.current = objectUrl;
      const player = new Audio(objectUrl);
      playbackRef.current = player;
      try {
        await player.play();
        setShowPlayButton(false);
      } catch (error) {
        setShowPlayButton(true);
      }
    } catch (error) {
      if (isCanceled(error)) {
        return;
      }
      setWarning((current) => current || "推荐语已生成，但语音播放失败，请阅读文字结果。");
    }
  }

  async function handleManualPlay() {
    const player = playbackRef.current;
    if (!player) {
      return;
    }
    try {
      await player.play();
      setShowPlayButton(false);
    } catch (error) {
      setShowPlayButton(true);
    }
  }

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>按住说话。录音完成后会依次上传、识别、提取、找店并生成推荐，不会重复提交付费请求。</p>

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
        onError={handleRecordError}
      />
      {recordError ? <p className="status error">{recordError}</p> : null}
      {busy ? <p className="hint-block">处理中，请勿重复提交。再次录音会开始新一轮并忽略上一轮结果。</p> : null}

      <StatusBar
        stage={statusError ? "" : STAGE_LABELS[stage] || ""}
        message={statusMessage}
        isError={statusError}
      />

      <RecordingPreview recording={recording} />
      <ResultPanel
        transcript={transcript}
        extract={extract}
        pois={pois}
        replyText={replyText}
        warning={warning}
        showPlayButton={showPlayButton}
        onPlay={handleManualPlay}
      />

      <section className="health">
        <p>后端地址：http://localhost:8003{healthOk ? "（已连通）" : ""}</p>
        <button type="button" onClick={checkHealth} disabled={busy}>
          检查后端健康状态
        </button>
        <p className="status">{healthMessage}</p>
      </section>
    </main>
  );
}
