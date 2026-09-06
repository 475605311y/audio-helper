export const MIN_DURATION_MS = 1000;
export const MAX_DURATION_MS = 60_000;
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm"];

export function detectSupportedMimeType() {
  if (
    typeof MediaRecorder === "undefined" ||
    typeof MediaRecorder.isTypeSupported !== "function"
  ) {
    return null;
  }
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function extensionForMime(mimeType) {
  if (mimeType?.includes("ogg")) {
    return "ogg";
  }
  return "webm";
}

export function stopStream(stream) {
  if (!stream) {
    return;
  }
  for (const track of stream.getTracks()) {
    track.stop();
  }
}

export function validateRecording({ blob, durationMs }) {
  if (!blob || blob.size === 0) {
    return { ok: false, message: "录制失败，没有得到有效音频，请重试。" };
  }
  if (durationMs < MIN_DURATION_MS) {
    return { ok: false, message: "录音需在1到60秒之间，请重新录制。" };
  }
  if (durationMs > MAX_DURATION_MS + 1000) {
    return { ok: false, message: "录音需在1到60秒之间，请重新录制。" };
  }
  if (blob.size > MAX_FILE_BYTES) {
    return { ok: false, message: "录音文件超过5MB，请缩短录音后重试。" };
  }
  return { ok: true };
}

export function messageForGetUserMediaError(error) {
  if (error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError") {
    return "无法使用麦克风，请允许浏览器访问麦克风后重试。";
  }
  if (error?.name === "NotFoundError" || error?.name === "DevicesNotFoundError") {
    return "没有找到可用的麦克风，请接入设备后重试。";
  }
  return "录制失败，请重试。";
}
