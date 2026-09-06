import { extensionForMime } from "../recording.js";

export default function RecordingPreview({ recording }) {
  if (!recording) {
    return null;
  }

  const extension = extensionForMime(recording.mimeType);
  const seconds = (recording.durationMs / 1000).toFixed(1);
  const sizeKb = (recording.blob.size / 1024).toFixed(1);
  const fileName = `meetup-recording.${extension}`;

  return (
    <section className="preview">
      <h2>本地试听</h2>
      <p>
        时长 {seconds} 秒，大小 {sizeKb} KB，格式 {recording.mimeType}
      </p>
      <audio controls src={recording.url} />
      <p>
        <a href={recording.url} download={fileName}>
          下载录音文件
        </a>
        <span className="hint">（本地录音备份，查找时只会上传这一份）</span>
      </p>
    </section>
  );
}
