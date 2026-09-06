export default function StatusBar({ stage, message, isError }) {
  return (
    <p className={isError ? "status error" : "status"}>
      {stage ? <strong>{stage} </strong> : null}
      {message}
    </p>
  );
}
