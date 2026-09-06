export default function ResultPanel({
  transcript,
  extract,
  pois,
  replyText,
  warning,
  showPlayButton,
  onPlay,
}) {
  const hasContent = transcript || extract || (pois && pois.length) || replyText;
  if (!hasContent) {
    return null;
  }

  return (
    <section className="results">
      {transcript ? (
        <div>
          <h2>识别文字</h2>
          <p>{transcript}</p>
        </div>
      ) : null}

      {extract ? (
        <div>
          <h2>提取信息</h2>
          <ul>
            <li>地点 A：{extract.city_a} {extract.address_a}</li>
            <li>地点 B：{extract.city_b} {extract.address_b}</li>
            <li>类别：{extract.category}</li>
          </ul>
        </div>
      ) : null}

      {pois && pois.length ? (
        <div>
          <h2>候选店铺</h2>
          <p className="hint-block">距离为到地理中点的米数，不表示两人出行时间相同。</p>
          <ol>
            {pois.slice(0, 3).map((poi, index) => (
              <li key={`${poi.name}-${index}`}>
                <strong>{poi.name}</strong>
                <div>{poi.address}</div>
                <div>距离中点 {poi.distance_to_midpoint_m} 米</div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {replyText ? (
        <div>
          <h2>推荐语</h2>
          <p>{replyText}</p>
          {warning ? <p className="status error">{warning}</p> : null}
          {showPlayButton ? (
            <button type="button" onClick={onPlay}>
              播放推荐语音
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
