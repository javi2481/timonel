// UploadBar — selector de imagenes_muestra + subir foto, limpiar, status.
import { useEffect, useRef, useState } from "react";
import { listMedia, type MediaItem } from "../api/client";
import type { SessionStatus } from "../state/session";

const STATUS_LABEL: Record<SessionStatus, string> = {
  idle: "Sin foto — elegí una muestra o subí",
  uploading: "Cargando…",
  processing: "Procesando…",
  ready: "Listo",
  degraded: "Degradado (PaddleX no disponible)",
  empty: "Completo — sin detecciones",
  error: "Error",
};

function sortMediaItems(items: MediaItem[]): MediaItem[] {
  return [...items].sort((a, b) => {
    const aDemo = a.name.startsWith("demo_") ? 0 : 1;
    const bDemo = b.name.startsWith("demo_") ? 0 : 1;
    if (aDemo !== bDemo) return aDemo - bDemo;
    return a.name.localeCompare(b.name);
  });
}

interface Props {
  status: SessionStatus;
  mediaName: string | null;
  errorMessage: string | null;
  onSelect: (name: string) => void;
  onUpload: (file: File) => void;
  onClear: () => void;
  onRetry: () => void;
}

export function UploadBar({
  status,
  mediaName,
  errorMessage,
  onSelect,
  onUpload,
  onClear,
  onRetry,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [items, setItems] = useState<MediaItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await listMedia();
        if (!cancelled) {
          setItems(sortMediaItems(list.filter((it) => it.type === "image")));
        }
      } catch {
        if (!cancelled) setItems([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

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
  const selectValue =
    mediaName && items.some((it) => it.name === mediaName) ? mediaName : "";

  return (
    <div className="tm-upload-bar">
      <label className="tm-media-select-label">
        <span className="tm-sr-only">Foto de imagenes_muestra</span>
        <select
          className="tm-media-select"
          value={selectValue}
          disabled={busy || items.length === 0}
          onChange={(e) => {
            const name = e.target.value;
            if (name) onSelect(name);
          }}
        >
          <option value="">
            {items.length === 0
              ? "Sin fotos en imagenes_muestra"
              : "Elegir foto del proyecto…"}
          </option>
          {items.map((it) => (
            <option key={it.name} value={it.name}>
              {it.name}
            </option>
          ))}
        </select>
      </label>
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
