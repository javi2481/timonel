# Onboarding Clone → Docker → Prueba — Plan de implementación

> **Para agentes de implementación:** usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` y ejecutar cada checkbox en orden.

**Objetivo:** lograr que una persona con Docker Desktop/Compose v2 pueda clonar el repositorio, levantar un stack core y probar una inferencia real siguiendo solo el README; el stack completo quedará disponible mediante un tutorial y un profile `full`.

**Arquitectura:** el Compose base contendrá `adapter`, `bridge`, vehículos y objetos. Las capacidades restantes se moverán al profile `full`, con un archivo de entorno propio. La SPA se servirá desde el artefacto construido en la imagen, habrá una imagen de demostración versionada y un smoke portable comprobará el recorrido completo.

**Stack:** Docker Compose v2, FastAPI, PaddleX, React/Vite, Python 3.12 y GitHub Actions.

## Restricciones globales

- El comando principal debe funcionar en PowerShell y Bash sin Node ni Python instalados en el host.
- `docker compose up --build --wait` debe levantar inferencia real; no una demo sintética.
- El stack core incluye `adapter`, `bridge`, `paddlex` (vehículos) y `paddlex-objects`.
- El profile `full` agrega OCR, caras, peatones, escena, pose, face ID, clasificación, instancias, objetos pequeños, anomalías y open-vocabulary.
- No versionar secretos, índices biométricos ni modelos.
- La imagen de muestra debe tener licencia redistribuible y atribución dentro del repositorio.
- El stack normal no debe montar `/var/run/docker.sock`; lifecycle seguirá siendo una configuración avanzada.

---

## Fase 1: Definir y validar los dos modos de ejecución

### Tarea 1: Convertir el Compose base en el stack core

**Archivos:**
- Modificar: `docker-compose.yml`
- Modificar: `.env.example`
- Crear: `.env.full.example`
- Crear: `tests/test_compose_onboarding.py`

**Resultado:** `docker compose up --build --wait` levanta únicamente los cuatro servicios del core; `--profile full --env-file .env.full.example` incorpora el resto.

- [ ] Escribir pruebas que ejecuten `docker compose config --services` para el modo core y `docker compose --profile full --env-file .env.full.example config --services` para full.
- [ ] Exigir en la prueba que core contenga exactamente `adapter`, `bridge`, `paddlex` y `paddlex-objects`.
- [ ] Exigir que full incluya las capacidades adicionales y que ningún puerto publicado se repita.
- [ ] Ejecutar `python tests/test_compose_onboarding.py` y confirmar que falla con el Compose actual.
- [ ] Añadir `profiles: ["full"]` a las capacidades no core y mantener sin profile los cuatro servicios core.
- [ ] Cambiar `.env.example` para que represente core: capacidades extra en `false`, cascada conservadora activa y lifecycle desactivado.
- [ ] Crear `.env.full.example` con las capacidades full activas, dejando `FACE_ID_INDEX_KEY` vacío y documentado como requisito para reconocimiento de identidad.
- [ ] Hacer que `bridge.depends_on` espere el health de `adapter`, `paddlex` y `paddlex-objects`.
- [ ] Ejecutar las pruebas de Compose y `docker compose config --quiet`.
- [ ] Commit sugerido: `feat(compose): add core default and full profile`.

### Tarea 2: Separar opciones avanzadas que hoy chocan con el arranque normal

**Archivos:**
- Modificar: `docker-compose.yml`
- Crear: `compose.gpu.yml`
- Modificar: `tests/test_compose_onboarding.py`

**Resultado:** GPU sustituye al servicio CPU en vez de publicar otro `:8080`, demo no arranca dos bridges y Docker socket no se monta en el flujo normal.

- [ ] Añadir pruebas de configuración para detectar puertos duplicados y más de un servicio bridge por escenario.
- [ ] Mover la sustitución GPU a `compose.gpu.yml`; el tutorial usará `docker compose -f docker-compose.yml -f compose.gpu.yml up --build`.
- [ ] Definir demo como comando explícito de servicios (`adapter bridge-demo`) o mediante un override que excluya `bridge`; no presentar `--profile demo up` como comando seguro.
- [ ] Quitar el mount permanente de Docker socket del bridge base.
- [ ] Documentar que lifecycle requiere un override avanzado separado antes de volver a habilitar `ENABLE_CONTAINER_LIFECYCLE`.
- [ ] Ejecutar las matrices core, full, GPU y demo de `tests/test_compose_onboarding.py`.
- [ ] Commit sugerido: `fix(compose): isolate gpu demo and lifecycle modes`.

---

## Fase 2: Garantizar una UI y una muestra utilizables en un clon limpio

### Tarea 3: Evitar que el bind mount oculte la SPA construida

**Archivos:**
- Modificar: `docker-compose.yml`
- Revisar/modificar: `adapter/Dockerfile`
- Crear: `scripts/smoke_onboarding.py`

**Resultado:** `/` redirige a `/app/` y `/app/` sirve la SPA desde un checkout sin `adapter/ui/spa/index.html` local.

- [ ] Añadir al smoke aserciones HTTP para `/` (redirect), `/app/`, un asset Vite referenciado por el HTML y `/health`.
- [ ] Ejecutar el smoke contra el Compose actual desde un checkout limpio y registrar el fallo esperado de `/app/` si el bind mount sigue activo.
- [ ] Eliminar el bind mount completo `./adapter:/app/adapter` del Compose base; la imagen será la fuente del código y de la SPA.
- [ ] Conservar únicamente el volumen de media requerido para subir y seleccionar imágenes.
- [ ] Confirmar que `adapter/Dockerfile` copia el build Vite a `/app/adapter/ui/spa` y que no requiere Node en runtime.
- [ ] Reconstruir `adapter` y ejecutar `python scripts/smoke_onboarding.py --ui-only`.
- [ ] Commit sugerido: `fix(adapter): serve packaged spa in clean clones`.

### Tarea 4: Incorporar una imagen de demostración redistribuible

**Archivos:**
- Modificar: `.gitignore`
- Crear: `imagenes_muestra/demo-street.jpg`
- Modificar: `imagenes_muestra/README.md`
- Crear: `imagenes_muestra/LICENSE.md`
- Modificar: `scripts/smoke_onboarding.py`

**Resultado:** el repositorio contiene una muestra útil para vehículos/objetos y el smoke la procesa sin FiftyOne ni descargas adicionales.

- [ ] Seleccionar una imagen pequeña con vehículo u objeto reconocible y licencia compatible; registrar autor, fuente, licencia y cualquier modificación.
- [ ] Añadir una excepción específica en `.gitignore` para la muestra y su licencia, sin habilitar el versionado general de uploads.
- [ ] Cambiar el smoke para enviar la imagen por `POST /media/upload`, en lugar de depender de nombres `fo_*` externos.
- [ ] Esperar hasta `generation == last_ingest_generation`.
- [ ] Verificar esquema de `/events` y que `/preview.jpg` sea un JPEG distinto del placeholder.
- [ ] Limpiar la media mediante `POST /media/clear` al terminar, incluso si falla una aserción.
- [ ] Ejecutar el smoke completo contra el stack core.
- [ ] Commit sugerido: `test(onboarding): add licensed sample and portable smoke`.

---

## Fase 3: Documentar el recorrido principal y el stack completo

### Tarea 5: Reescribir el inicio rápido para Windows y Unix

**Archivos:**
- Modificar: `README.md`
- Modificar: `adapter/ui/README.md`

**Resultado:** un usuario nuevo puede completar el flujo core sin conocer la arquitectura interna.

- [ ] Añadir prerrequisitos: Docker Desktop/Engine, Compose v2, conexión a Internet para el primer build, arquitectura soportada, espacio en disco y RAM recomendada.
- [ ] Documentar PowerShell:

  ```powershell
  Copy-Item .env.example .env
  docker compose up --build --wait
  python scripts/smoke_onboarding.py
  ```

- [ ] Documentar Bash:

  ```bash
  cp .env.example .env
  docker compose up --build --wait
  python3 scripts/smoke_onboarding.py
  ```

- [ ] Explicar la alternativa sin Python: abrir `http://localhost:8000`, seleccionar/subir `demo-street.jpg` y esperar overlay/eventos.
- [ ] Explicar cómo inspeccionar progreso con `docker compose ps` y `docker compose logs -f bridge`.
- [ ] Indicar que el primer arranque descarga imágenes/modelos y puede tardar varios minutos.
- [ ] Corregir el mapa de servicios y eliminar referencias obsoletas a profiles `extended` y `experimental`.
- [ ] Documentar `/app/` como única UI (SPA incluida en la imagen); `/` redirige a `/app/`.
- [ ] Validar todos los comandos copiándolos desde un checkout limpio en PowerShell y Bash.
- [ ] Commit sugerido: `docs: add clone-to-core onboarding`.

### Tarea 6: Crear el tutorial del stack completo

**Archivos:**
- Crear: `docs/onboarding-full-stack.md`
- Modificar: `README.md`
- Modificar: `.env.full.example`

**Resultado:** el usuario puede pasar conscientemente de core a las 13 capacidades, con requisitos y limitaciones explícitos.

- [ ] Documentar el comando:

  ```powershell
  Copy-Item .env.full.example .env
  docker compose --profile full up --build --wait
  ```

- [ ] Incluir requisitos de RAM/CPU, tiempo de cold start, descarga de modelos y puertos `8080–8093`.
- [ ] Explicar qué agrega cada capacidad y cuáles requieren configuración adicional, especialmente face ID.
- [ ] Explicar que `open-vocab` también sirve a signs y no debe pausarse independientemente.
- [ ] Añadir procedimientos de diagnóstico para `unhealthy`, `OOMKilled`, timeout y modelos aún descargándose.
- [ ] Añadir apagado y limpieza segura: `docker compose --profile full down`; separar claramente la eliminación opcional de volúmenes de modelos.
- [ ] Enlazar el tutorial desde el README después del flujo core, no antes.
- [ ] Ejecutar `docker compose --profile full --env-file .env.full.example config --quiet`.
- [ ] Commit sugerido: `docs: add full-stack onboarding guide`.

---

## Fase 4: Prevenir regresiones

### Tarea 7: Añadir gates de onboarding a CI

**Archivos:**
- Modificar: `.github/workflows/ci.yml`
- Modificar: `tests/test_compose_onboarding.py`
- Modificar: `scripts/smoke_onboarding.py`
- Modificar: `tests/README.md`

**Resultado:** CI detecta perfiles rotos, puertos duplicados, SPA que no compila y documentación desalineada.

- [ ] Añadir a CI `docker compose config --quiet` para core y full.
- [ ] Ejecutar `python tests/test_compose_onboarding.py`.
- [ ] Añadir `npm ci` y `npm run build` en `adapter/ui/spa-src`.
- [ ] Añadir una prueba UI liviana iniciando solo el adapter con dependencias simuladas o probando el artefacto estático; no descargar modelos PaddleX en cada PR.
- [ ] Mantener el smoke real con PaddleX como comando manual documentado o workflow disparado manualmente.
- [ ] Actualizar `tests/README.md` con la diferencia entre tests unitarios, smoke UI y smoke real core/full.
- [ ] Ejecutar localmente la misma secuencia de CI y confirmar árbol limpio.
- [ ] Commit sugerido: `ci: validate onboarding paths`.

## Validación final

- [ ] En un checkout limpio de Windows: copiar `.env.example`, ejecutar Compose y obtener `/app/`, `/health`, eventos y preview procesado (`/` → redirect).
- [ ] Repetir el recorrido core en Bash.
- [ ] Confirmar que core levanta cuatro servicios funcionales y no monta Docker socket.
- [ ] Confirmar que full agrega todas las capacidades sin colisiones de puertos.
- [ ] Confirmar que demo tiene un solo bridge y GPU sustituye al servicio CPU.
- [ ] Confirmar que README y `docs/onboarding-full-stack.md` contienen únicamente comandos probados.
- [ ] Ejecutar CI completa y el smoke real core antes del merge.

## Fuera de alcance

- Distribuir modelos dentro del repositorio o de las imágenes.
- Automatizar la creación de índices de reconocimiento facial.
- Optimizar precisión/latencia de los modelos.
- Garantizar el stack full en equipos por debajo del requisito de RAM documentado.
