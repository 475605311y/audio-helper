import axios from "axios";

export const API_BASE_URL = "http://localhost:8003";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 3000,
});

export const TIMEOUTS = {
  health: 3000,
  upload: 12_000,
  asr: 25_000,
  extract: 20_000,
  search: 18_000,
  finalize: 32_000,
  audio: 8000,
};

export function getHealth(config = {}) {
  return api.get("/health", { timeout: TIMEOUTS.health, ...config });
}

export function uploadAudio(file, config = {}) {
  const form = new FormData();
  form.append("file", file);
  return api.post("/upload", form, {
    timeout: TIMEOUTS.upload,
    ...config,
  });
}

export function recognizeAudio(audioId, config = {}) {
  return api.post("/asr", { audio_id: audioId }, { timeout: TIMEOUTS.asr, ...config });
}

export function extractMeetup(text, city, config = {}) {
  return api.post(
    "/extract",
    { text, city },
    { timeout: TIMEOUTS.extract, ...config },
  );
}

export function searchMeetup(fields, config = {}) {
  return api.post("/search", fields, { timeout: TIMEOUTS.search, ...config });
}

export function finalizeMeetup(searchId, config = {}) {
  return api.post(
    "/finalize",
    { search_id: searchId },
    { timeout: TIMEOUTS.finalize, ...config },
  );
}

export function resolveAudioUrl(audioUrl) {
  if (!audioUrl) {
    return "";
  }
  if (audioUrl.startsWith("http://") || audioUrl.startsWith("https://")) {
    return audioUrl;
  }
  if (audioUrl.startsWith("/")) {
    return `${API_BASE_URL}${audioUrl}`;
  }
  return audioUrl;
}

export function downloadAudio(audioUrl, config = {}) {
  return axios.get(resolveAudioUrl(audioUrl), {
    responseType: "blob",
    timeout: TIMEOUTS.audio,
    ...config,
  });
}

export function isCanceled(error) {
  return axios.isCancel(error) || error.code === "ERR_CANCELED";
}

export function readApiError(error) {
  const payload = error.response?.data;
  if (
    payload &&
    typeof payload === "object" &&
    !ArrayBuffer.isView(payload) &&
    !(typeof Blob !== "undefined" && payload instanceof Blob) &&
    payload.error?.message
  ) {
    return payload.error.message;
  }
  if (error.code === "ECONNABORTED" || /timeout/i.test(error.message || "")) {
    return "请求超时，请稍后重试。";
  }
  if (!error.response) {
    return "网络连接失败，请检查后端是否已启动。";
  }
  return "请求失败，请稍后重试。";
}
