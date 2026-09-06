import { useEffect, useRef, useState } from "react";
import {
  MAX_DURATION_MS,
  detectSupportedMimeType,
  messageForGetUserMediaError,
  stopStream,
  validateRecording,
} from "../recording.js";

export default function RecordButton({ onRecordingReady, onError }) {
  const mimeType = detectSupportedMimeType();
  const [recording, setRecording] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const sessionRef = useRef(null);
  const startTokenRef = useRef(0);

  useEffect(() => {
    return () => {
      teardown(sessionRef.current, { discard: true });
      sessionRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!recording) {
      return undefined;
    }

    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        cancelRecording();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [recording]);

  function reportError(message) {
    onError(message);
  }

  function teardown(session, { discard }) {
    if (!session) {
      return;
    }
    session.discard = discard || session.discard;
    window.clearTimeout(session.maxTimer);
    window.clearInterval(session.tickTimer);
    if (session.recorder && session.recorder.state !== "inactive") {
      session.recorder.stop();
    } else {
      stopStream(session.stream);
    }
  }

  async function startRecording() {
    if (!mimeType || sessionRef.current) {
      return;
    }
    const startToken = startTokenRef.current + 1;
    startTokenRef.current = startToken;
    onError("");

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (startTokenRef.current === startToken) {
        reportError(messageForGetUserMediaError(error));
      }
      return;
    }

    if (startTokenRef.current !== startToken) {
      stopStream(stream);
      return;
    }

    const chunks = [];
    let recorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch (error) {
      stopStream(stream);
      reportError("录制失败，请重试。");
      return;
    }

    const session = {
      stream,
      recorder,
      chunks,
      startedAt: Date.now(),
      discard: false,
      maxTimer: 0,
      tickTimer: 0,
    };
    sessionRef.current = session;
    if (startTokenRef.current !== startToken) {
      teardown(session, { discard: true });
      return;
    }

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        session.chunks.push(event.data);
      }
    };

    recorder.onerror = () => {
      session.discard = true;
      reportError("录制失败，请重试。");
      teardown(session, { discard: true });
    };

    recorder.onstop = () => {
      stopStream(session.stream);
      window.clearTimeout(session.maxTimer);
      window.clearInterval(session.tickTimer);
      if (sessionRef.current === session) {
        sessionRef.current = null;
      }
      setRecording(false);
      setElapsedMs(0);

      if (session.discard) {
        return;
      }

      const durationMs = Date.now() - session.startedAt;
      const blob = new Blob(session.chunks, { type: mimeType });
      const result = validateRecording({ blob, durationMs });
      if (!result.ok) {
        reportError(result.message);
        return;
      }
      onRecordingReady({ blob, durationMs, mimeType });
    };

    try {
      recorder.start();
    } catch (error) {
      stopStream(stream);
      sessionRef.current = null;
      reportError("录制失败，请重试。");
      return;
    }

    session.maxTimer = window.setTimeout(() => {
      stopRecording();
    }, MAX_DURATION_MS);
    session.tickTimer = window.setInterval(() => {
      setElapsedMs(Date.now() - session.startedAt);
    }, 200);

    setRecording(true);
    setElapsedMs(0);
  }

  function stopRecording() {
    startTokenRef.current += 1;
    teardown(sessionRef.current, { discard: false });
  }

  function cancelRecording() {
    startTokenRef.current += 1;
    teardown(sessionRef.current, { discard: true });
    setRecording(false);
    setElapsedMs(0);
    onError("已取消录音。");
  }

  function onPointerDown(event) {
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    startRecording();
  }

  function onPointerUp(event) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    stopRecording();
  }

  function onPointerCancel() {
    stopRecording();
  }

  if (!mimeType) {
    return (
      <p className="status error">
        当前浏览器不支持 WebM/Opus 录音，请更换 Chrome 或 Firefox 后重试。
      </p>
    );
  }

  const seconds = Math.min(60, Math.floor(elapsedMs / 1000));

  return (
    <div className="record-wrap">
      <button
        type="button"
        className={recording ? "record-button recording" : "record-button"}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        onContextMenu={(event) => event.preventDefault()}
      >
        {recording ? `正在录音 ${seconds}s，松开结束` : "按住说话"}
      </button>
      {recording ? <p className="hint">按 Esc 取消录音</p> : null}
    </div>
  );
}
