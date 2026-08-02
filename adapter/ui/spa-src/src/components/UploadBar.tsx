// UploadBar — subir foto, limpiar, status.
import { useEffect, useRef, useState } from "react";
import type { SessionStatus } from "../state/session";

const STATUS_LABEL: Record<SessionStatus, string> = {
  idle: "Sin foto — subí una imagen",
  uploading: "Cargando…",
  processing: "Procesando…",
  ready: "Listo",
  degraded: "Degradado (PaddleX no disponible)",
  empty: "Completo — sin detecciones",
  error: "Error",
};

interface Props {
  status: SessionStatus;
  errorMessage: string | null;
  onUpload: (file: File) => void;
  onClear: () => void;
  onRetry: () => void;
}

export function UploadBar({
  status,
  errorMessage,
  onUpload,
  onClear,
  onRetry,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (status !== "uploading" && status !== "processing") {
      setElapsedSec(0);
      return;
    }
    const started = Date.now();
    setElapsedSec(0);
    const id = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - started) / 1000));
    }, 500);
    return () => window.clearInterval(id);
  }, [status]);

  const showTimer = status === "uploading" || status === "processing";
  const busy = status === "uploading" || status === "processing";

  return (
    <div className="tm-upload-bar">
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.bmp,image/jpeg,image/png,image/bmp"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.target.value = "";
        }}
      />
      <button
        className="tm-btn tm-btn-primary"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        Subir foto
      </button>
      <button className="tm-btn" onClick={onClear} disabled={status === "idle"}>
        Limpiar
      </button>
      {status === "error" && (
        <button className="tm-btn" onClick={onRetry}>
          Reintentar
        </button>
      )}
      <span className={`tm-status-pill tm-status-${status}`}>
        {STATUS_LABEL[status]}
        {showTimer ? ` ${elapsedSec}s` : ""}
        {status === "error" && errorMessage ? `: ${errorMessage}` : ""}
      </span>
    </div>
  );
}
