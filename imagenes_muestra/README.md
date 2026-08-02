# imagenes_muestra/ — fotos de prueba (van con el clone)

Mount de adapter/bridge: `./imagenes_muestra` → `/media/images`.

## Onboarding (versionado)

Todas las fotos de esta carpeta (`demo_*.jpg` y `fo_*.jpg`) están **en el
repo**. Quien clone Timonel las recibe en su PC. En la UI usá el **selector**
del header (lista `GET /media/list`); no hace falta buscar fotos en internet.

| | |
|--|--|
| Manifiesto demos | [`manifest_demo.json`](manifest_demo.json) (`requires`: metadata histórica) |
| Atribución demos | [`LICENSE.md`](LICENSE.md) |
| Selector SPA | elige por nombre; no depende del file picker del SO |

Con `scripts/full_up` / `docker compose up` todas las capas SPA están arriba.

## Mantenimiento (opcional)

Solo si querés **regenerar** demos Openverse:

```bash
python scripts/fetch_demo_images.py
```

No es un paso de onboarding.

## Layout

```text
imagenes_muestra/
  demo_XX_*.jpg     # onboarding (versionadas)
  fo_*.jpg          # muestras adicionales (versionadas)
  README.md LICENSE.md manifest_demo.json
```

## Thrash del media-watch

Muchos JPG en la raíz saturan el watch. Con ~60 fotos está OK si el warning
interno es ~40+; si sumás más eval local, preferí pausar adapter/bridge.

## Licencias

- Demos `demo_*`: CC0/PDM vía Openverse — ver `LICENSE.md`
- `fo_*`: packs de muestra del proyecto (uso local / smoke)
