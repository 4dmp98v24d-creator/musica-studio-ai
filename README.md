# Música Studio AI

Estudio web en español para separar MP3, WAV y M4A con **Demucs htdemucs**. FastAPI sirve la API y el frontend desde el mismo dominio. Mezclador Web Audio de cuatro pistas (voz, batería, bajo y otros), controles inmediatos, silencio, pausa, búsqueda y descargas WAV. Karaoke combina batería, bajo y otros con un control instrumental independiente. No usa Hugging Face Spaces ni servicios de separación pagos.

## Ejecutar con Docker

Requisitos recomendados: Linux x86_64, Docker Compose, 2–4 CPU, **8 GB de RAM** y 10 GB libres más espacio para audio. CPU funciona sin GPU, pero puede tardar más que la duración de la canción. Una cola procesa un trabajo a la vez, hasta tres trabajos pendientes/en curso. No iniciar múltiples workers ni réplicas con esta implementación.

```sh
git clone https://github.com/4dmp98v24d-creator/musica-studio-ai.git
cd musica-studio-ai
docker compose up -d --build
docker compose logs -f studio
curl http://127.0.0.1:8000/api/health
```

Abrir `http://localhost:8000` en la misma computadora. Para acceder desde teléfonos, publicar HTTPS como se explica abajo. La primera separación descarga los pesos públicos de Demucs desde los servidores de modelos de Meta (necesita salida HTTPS); se conservan en el volumen `models`. El endpoint health comprueba el servicio HTTP, **no confirma que los pesos estén descargados ni que la inferencia funcione**.

## Publicar una URL HTTPS para Safari

1. Conseguir un servidor Linux con los recursos anteriores, Docker y Caddy. Puede ser una computadora propia encendida o una VM. No se ha contratado ni aprovisionado hosting con este repositorio.
2. Ejecutar Compose. El puerto 8000 se limita a localhost; Caddy atenderá el tráfico externo.
3. Apuntar un dominio/subdominio a la IP pública del servidor. Abrir 80 y 443. Copiar `Caddyfile` a `/etc/caddy/Caddyfile`, sustituir `{$DOMAIN}` por el dominio real (por ejemplo `musica.ejemplo.com`) y recargar Caddy. Caddy obtiene y renueva el certificado automáticamente. El ejemplo supone Caddy instalado en el host, no en otro contenedor.
4. Comprobar `https://TU_DOMINIO/api/health`, cargar una canción corta y comprobar que termina en `ready`, escuchar las cuatro pistas, probar karaoke, volumen, silencio, búsqueda y descargas desde un iPhone real en Safari.
5. Comprobar reinicio y persistencia de los volúmenes. Revisar disco, RAM y registros; no borrar volúmenes si se quieren conservar modelos y trabajos aún vigentes.

Un túnel HTTPS desde una computadora propia también puede evitar abrir puertos, pero necesita un proveedor, configuración y mantener la computadora encendida; algunos proveedores exigen dominio o imponen límites. Una URL temporal no constituye hosting permanente.

### Alternativas de costo bajo o gratuito

- **Computadora propia + Docker + acceso HTTPS:** software gratuito, sin cuota de inferencia; consume electricidad, CPU y ancho de banda propios. La URL deja de funcionar al apagarla. El dominio puede tener costo.
- **VM gratuita disponible en un proveedor (por ejemplo Oracle Always Free):** sujeta a disponibilidad regional, alta/verificación, políticas de inactividad y cuotas que deben comprobarse al contratar. Elegir al menos 8 GB de RAM; las VM pequeñas de 512 MB/1 GB no son adecuadas. Este Dockerfile y las pruebas apuntan a x86_64; ARM requiere validar PyTorch y el build.
- **Créditos promocionales:** pueden servir para probar una VM con suficiente RAM, pero expiran y no garantizan funcionamiento gratuito permanente.
- **VPS de pago:** opción más predecible si no hay VM gratuita disponible; GPU es opcional. Este proyecto no reserva ni factura recursos.

GitHub Pages y hosting estático no ejecutan Demucs. Los planes gratuitos web con poca RAM, suspensión o tiempo máximo de ejecución suelen ser insuficientes. No se promete ningún plan gratuito de terceros: confirmar condiciones vigentes antes de elegirlo.

## Desarrollo sin Docker

Python **3.11**, FFmpeg/FFprobe y libsndfile instalados en el sistema:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

PyTorch y torchaudio deben tener versiones compatibles. Se fijan a 2.5.1 para evitar los cambios de backend de audio de versiones más recientes. CUDA requiere una imagen/configuración PyTorch compatible y `DEMUCS_DEVICE=cuda`; Compose está preparado para CPU.

## Configuración

| Variable | Valor por defecto | Uso |
|---|---|---|
| `DATA_DIR` | `/tmp/musica-studio` (`/data` en Docker) | Audio y estados persistidos |
| `TORCH_HOME` | caché de PyTorch (`/models` en Docker) | Pesos de modelos |
| `MAX_UPLOAD_MB` | 50 | Tamaño de archivo |
| `MAX_DURATION_SECONDS` | 600 | Duración máxima |
| `MAX_STORED_JOBS` | 10 | Capacidad total de sesiones guardadas |
| `RETENTION_HOURS` | 24 | Borrado automático de sesiones finalizadas |
| `PROCESS_TIMEOUT_SECONDS` | 3600 | Tiempo máximo de Demucs por canción |
| `DEMUCS_DEVICE` | cpu | CPU o CUDA configurada |
| `PORT` | 8000 | Puerto de la imagen Docker |

FFprobe valida la duración real y FFmpeg decodifica antes de inferir. El original se borra tras procesar incluso si hay error. Los WAV derivados permanecen hasta el vencimiento; el limpiador corre cada minuto. Los trabajos activos no se borran. Si el proceso muere, los trabajos interrumpidos se marcan con error al arrancar; el usuario debe volver a subirlos. Sesiones y resultados no se sincronizan entre servidores.

Los identificadores son secretos aleatorios de 192 bits: quien posea el enlace puede descargar el audio hasta que expire. No hay cuentas, recuperación de sesiones ni autorización por usuario. Antes de difundir un servicio personal, restringir acceso en el proxy (por ejemplo `basic_auth` de Caddy con contraseña hasheada), limitar peticiones y presupuesto de recursos. Para un servicio público multiusuario añadir autenticación, cuotas por usuario, cola externa, almacenamiento de objetos y monitoreo. Los límites globales actuales impiden llenar una cola infinita pero no sustituyen esas funciones.

Los WAV decodificados ocupan mucha más memoria que MP3/M4A. En teléfonos se recomiendan canciones cortas y cerrar otras pestañas; una canción larga puede exceder la memoria de Safari. El navegador carga cuatro buffers y los inicia con el mismo reloj AudioContext. Karaoke usa esos mismos buffers para evitar cargar una quinta copia; el instrumental descargable se suma con FFmpeg. Las mezclas muy fuertes pueden saturar: reducir volúmenes. Safari requiere un toque para iniciar audio; reproducción en segundo plano y descarga pueden comportarse distinto en cada versión de iOS. No se ofrece letra sincronizada.

## Pruebas

```sh
pip install httpx==0.28.1
python -m unittest discover -s tests -v
node --check frontend/app.js
# Prueba opcional real: descarga pesos y consume CPU/RAM
OMP_NUM_THREADS=2 python tests/smoke_demucs.py
```

`tests/smoke_demucs.py` separa un WAV sintético de dos segundos usando el modelo real y comprueba formato, duración y valores finitos de las cinco descargas. No mide calidad musical. La CI corre pruebas de API y construcción de Docker; la inferencia real es optativa para evitar descargas pesadas en cada commit. Consultar `VALIDATION.md` para los resultados obtenidos en esta entrega.

Demucs y sus dependencias conservan sus propias licencias; revisar las condiciones de modelos y el derecho a procesar cada canción antes de operar un servicio público.
