// App — shell SPA: inferencia en background; toggles = solo visibilidad.
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCapabilities,
  putCapabilities,
  type CapabilityEntry,
} from "./api/client";
import { AnalyticsRow } from "./components/AnalyticsRow";
import { CapabilityPanel } from "./components/CapabilityPanel";
import { EventsTable } from "./components/EventsTable";
import { Legend } from "./components/Legend";
import { PhotoCanvas } from "./components/PhotoCanvas";
import { UploadBar } from "./components/UploadBar";
import { useSession } from "./state/session";

export function App() {
  const { state, upload, clear, retry } = useSession();
  const [visibility, setVisibility] = useState<Record<string, boolean>>({});
  const [catalog, setCatalog] = useState<Record<string, CapabilityEntry>>({});
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);

  const refreshCatalog = useCallback(async () => {
    try {
      const res = await getCapabilities();
      setCatalog(res.capabilities);
    } catch {
      // Adapter offline: keep last catalog.
    }
  }, []);

  useEffect(() => {
    void refreshCatalog();
  }, [refreshCatalog]);

  // Poll catalog while any capa is warming (active && !serving).
  useEffect(() => {
    const warming = Object.values(catalog).some(
      (c) => c.available && c.active && !c.serving && !c.error,
    );
    if (!warming) return;
    const id = window.setInterval(() => void refreshCatalog(), 2000);
    return () => window.clearInterval(id);
  }, [catalog, refreshCatalog]);

  // Reset visibility on generation bump (cajas ocultas hasta que el usuario elija).
  useEffect(() => {
    setVisibility({});
    setHoveredId(null);
    setSelectedId(null);
    setImageLoaded(false);
  }, [state.generation]);

  useEffect(() => {
    void refreshCatalog();
  }, [state.generation, refreshCatalog]);

  const availableCapCount = useMemo(
    () => Object.values(catalog).filter((c) => c.available).length,
    [catalog],
  );

  const hitEntityTypes = useMemo(() => {
    const present = new Set(state.events.map((e) => e.entity_type));
    return [...present];
  }, [state.events]);

  const analysisComplete =
    state.status === "ready" ||
    state.status === "degraded" ||
    state.status === "empty";

  const showHeaderProgress =
    state.status === "uploading" || state.status === "processing";
  const headerProgressLabel =
    state.status === "uploading" || (state.status === "processing" && !imageLoaded)
      ? "Cargando foto…"
      : "Analizando imagen…";
  const headerProgressSub =
    state.status === "processing" && imageLoaded
      ? `${availableCapCount} capacidad${availableCapCount === 1 ? "" : "es"} disponible${availableCapCount === 1 ? "" : "s"}`
      : null;

  const onImageLoaded = useCallback((loaded: boolean) => {
    setImageLoaded(loaded);
  }, []);

  const onShowHits = useCallback(() => {
    setVisibility((prev) => {
      const next = { ...prev };
      for (const t of hitEntityTypes) next[t] = true;
      return next;
    });
  }, [hitEntityTypes]);

  const onHideAll = useCallback(() => {
    setVisibility({});
  }, []);

  const onActivate = useCallback(
    async (entityType: string) => {
      try {
        await putCapabilities({ [entityType]: true });
        await refreshCatalog();
      } catch {
        // Keep catalog; user can retry.
      }
    },
    [refreshCatalog],
  );

  return (
    <div className="tm-app">
      <header className="tm-header">
        <div className="tm-brand">
          <h1>Timonel</h1>
          <p className="tm-brand-sub">
            Usa PaddleX (modelos de visión open-source) para detectar objetos,
            caras, pose y texto en una foto, y mostrar todo junto en un solo
            panel.
          </p>
        </div>
        <UploadBar
          status={state.status}
          errorMessage={state.errorMessage}
          onUpload={(file) => void upload(file)}
          onClear={() => void clear()}
          onRetry={retry}
        />
      </header>

      {showHeaderProgress && (
        <div
          className="tm-header-progress"
          role="progressbar"
          aria-busy="true"
          aria-label={headerProgressLabel}
        >
          <div className="tm-header-progress-copy">
            <span className="tm-header-progress-label">{headerProgressLabel}</span>
            {headerProgressSub && (
              <span className="tm-header-progress-sub">{headerProgressSub}</span>
            )}
          </div>
          <div className="tm-progress-indeterminate" aria-hidden>
            <div className="tm-progress-indeterminate-bar" />
          </div>
        </div>
      )}

      <div className="tm-layout">
        <aside className="tm-sidebar">
          <div className="tm-card-h">Capacidades</div>
          <CapabilityPanel
            events={state.events}
            visibility={visibility}
            catalog={catalog}
            status={state.status}
            onToggleVisible={(entityType, visible) =>
              setVisibility((prev) => ({ ...prev, [entityType]: visible }))
            }
            onActivate={(entityType) => void onActivate(entityType)}
            onShowHits={onShowHits}
            onHideAll={onHideAll}
          />
        </aside>

        <main className="tm-main">
          {state.status === "idle" ? (
            <div className="tm-stage-idle" role="status">
              <div className="tm-stage-idle-inner">
                <h2 className="tm-stage-idle-title">Timonel</h2>
                <p className="tm-stage-idle-copy">
                  Subí tu foto para que PaddleX la analice. Las capas quedan
                  activas; vos elegís cuáles mostrar en la imagen.
                </p>
              </div>
            </div>
          ) : (
            <>
              <PhotoCanvas
                generation={state.generation}
                events={state.events}
                visibility={visibility}
                hoveredId={hoveredId}
                selectedId={selectedId}
                onHover={setHoveredId}
                onSelect={setSelectedId}
                status={state.status}
                errorMessage={state.errorMessage}
                onRetry={retry}
                onImageLoaded={onImageLoaded}
              />
              <Legend events={state.events} visibility={visibility} />
            </>
          )}
        </main>
      </div>

      <AnalyticsRow
        events={state.events}
        visibility={visibility}
        catalog={catalog}
        analysisComplete={analysisComplete}
      />

      <EventsTable
        events={state.events}
        visibility={visibility}
        hoveredId={hoveredId}
        selectedId={selectedId}
        onHover={setHoveredId}
        onSelect={setSelectedId}
      />
    </div>
  );
}
