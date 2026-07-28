// UploadBar — subir foto, dominio OV, limpiar, status + timer.
import { useEffect, useRef, useState } from "react";
import type { SessionStatus } from "../state/session";

const STATUS_LABEL: Record<SessionStatus, string> = {
  idle: "Sin foto — subí una imagen",
  uploading: "Subiendo…",
  processing: "Procesando…",
  ready: "Listo",
  degraded: "Degradado (PaddleX no disponible)",
  empty: "Completo — sin detecciones",
  error: "Error",
};

export const OV_DOMAIN_PRESETS: { id: string; label: string; prompt: string }[] = [
  { id: "general", label: "General", prompt: "" },
  {
    id: "epp",
    label: "EPP",
    prompt: "helmet,hard hat,safety vest,reflective vest,gloves,goggles",
  },
  {
    id: "obra",
    label: "Obra",
    prompt: "forklift,traffic cone,barricade,ladder,scaffold,pallet,generator",
  },
  {
    id: "hogar",
    label: "Hogar",
    prompt:
      "stapler,backpack,suitcase,umbrella,wheelchair,stroller,fire extinguisher",
  },
];

interface Props {
  status: SessionStatus;
  errorMessage: string | null;
  onUpload: (file: File, openVocabPrompt?: string | null) => void;
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
  const [domainId, setDomainId] = useState("general");
  const [customPrompt, setCustomPrompt] = useState("");
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

  const resolvePrompt = (): string | null => {
    const custom = customPrompt.trim();
    if (custom) return custom;
    const preset = OV_DOMAIN_PRESETS.find((p) => p.id === domainId);
    return preset?.prompt?.trim() || null;
  };

  const showTimer = status === "uploading" || status === "processing";

  return (
    <div className="vi-upload-bar">
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.bmp,image/jpeg,image/png,image/bmp"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file, resolvePrompt());
          e.target.value = "";
        }}
      />
      <button
        className="vi-btn vi-btn-primary"
        disabled={status === "uploading"}
        onClick={() => inputRef.current?.click()}
      >
        Subir foto
      </button>
      <button className="vi-btn" onClick={onClear} disabled={status === "idle"}>
        Limpiar
      </button>
      {status === "error" && (
        <button className="vi-btn" onClick={onRetry}>
          Reintentar
        </button>
      )}
      <div className="vi-domain-chips" title="Vocabulario open-vocab para esta foto">
        {OV_DOMAIN_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`vi-domain-chip${domainId === p.id && !customPrompt.trim() ? " on" : ""}`}
            onClick={() => {
              setDomainId(p.id);
              setCustomPrompt("");
            }}
          >
            {p.label}
          </button>
        ))}
      </div>
      <input
        className="vi-ov-prompt-input"
        type="text"
        placeholder="Prompt OV opcional…"
        value={customPrompt}
        onChange={(e) => setCustomPrompt(e.target.value)}
        title="Override libre; vacío usa el chip de dominio o el default del servidor"
      />
      <span className={`vi-status-pill vi-status-${status}`}>
        {STATUS_LABEL[status]}
        {showTimer ? ` ${elapsedSec}s` : ""}
        {status === "error" && errorMessage ? `: ${errorMessage}` : ""}
      </span>
    </div>
  );
}
