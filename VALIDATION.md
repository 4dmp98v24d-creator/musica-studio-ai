# Verificación de entrega — 28 de octubre de 2026

## Comprobado

- Instalación en Python 3.11 de requirements.txt, con PyTorch/torchaudio 2.5.1 CPU.
- Siete pruebas automáticas de API y audio: frontend/health, archivos vacíos/formatos rechazados/tamaño máximo, cola, control de descargas, capacidad/vencimiento, error ante audio inválido, reinicio de trabajos y decodificación real de MP3/WAV/M4A con FFmpeg.
- `node --check frontend/app.js` y `docker compose config --quiet` pasaron.
- Inferencia real de Demucs htdemucs: WAV estéreo sintético de dos segundos, cuatro stems e instrumental, 44.1 kHz, dimensiones esperadas y muestras finitas. Pesos descargados realmente. No se usó una respuesta simulada.
- Prueba de navegador Chromium con viewport móvil 390×844: carga HTTP real, inferencia, cuatro pistas, reproducción con cuatro fuentes, ganancia inmediata, silencio, cambio a karaoke, volumen instrumental aplicado a batería/bajo/otros, descarga WAV, reinicio y ausencia de errores JavaScript. Sin desbordamiento horizontal.
- Dockerfile construido con éxito. Contenedor ejecutado como usuario sin privilegios, puerto HTTP comprobado y estado Docker `healthy`.
- La misma prueba completa Chromium pasó contra el backend dentro del contenedor Docker, utilizando los pesos reales montados desde caché.

Scripts: `tests/test_api.py`, `tests/smoke_demucs.py` y `tests/browser_smoke.py`. El último requiere `pip install playwright`, `playwright install chromium`, backend iniciado y variable `BASE_URL` si se usa otro puerto. Los modelos de las pruebas están fuera del repositorio.

## Pendiente

- Prueba en un iPhone físico con Safari, un Android físico y canciones completas. La muestra sintética demuestra ejecución técnica, no calidad musical ni desempeño con canciones largas. No se midió separación perceptual.
- WebKit se descargó, pero su arranque quedó inicialmente bloqueado por dependencias nativas ausentes del entorno. Esto no equivale a una prueba de Safari real.
- Publicación HTTPS y verificación desde una red externa. No se aprovisionó un servidor permanente ni se asignó dominio.
- Revisión de controles de acceso y cuotas si se va a abrir al público. La implementación actual usa enlaces secretos por sesión, una cola local y límites globales; está pensada para una instancia pequeña.

## GitHub: bloqueo observado

El repositorio remoto estaba vacío. La integración devolvió metadata con permisos del usuario `push: true` y `admin: true`, pero la escritura efectiva falló:

- Contents API al intentar inicializar `.gitignore`: HTTP 403 `Resource not accessible by integration`.
- `git push -u origin main`: HTTP 403 `Permission ... denied`.

No se creó una rama remota, commit remoto ni pull request. No se inició GitHub Actions. Hay historial local y se entrega un bundle Git más un ZIP de código. Es necesario habilitar permiso de escritura de **Contents** para esta integración/repositorio y de **Workflows** para subir `.github/workflows/tests.yml`.

Una vez corregido el acceso, desde este directorio se puede ejecutar `git push -u origin main` para inicializar el repositorio vacío. El usuario autorizó la subida directa. También se conserva una rama local `feat/demucs-studio`.

Para recuperar el historial desde el bundle en otra computadora:

```sh
git clone /ruta/musica-studio-ai.bundle musica-studio-ai
cd musica-studio-ai
git remote set-url origin https://github.com/4dmp98v24d-creator/musica-studio-ai.git
git push -u origin main
```

No hay URL pública operativa como resultado de esta entrega.
