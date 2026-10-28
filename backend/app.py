import asyncio
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DATA = Path(os.getenv('DATA_DIR', '/tmp/musica-studio')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.getenv('MAX_UPLOAD_MB', '50')) * 1024 * 1024
MAX_SECONDS = int(os.getenv('MAX_DURATION_SECONDS', '600'))
TTL = int(os.getenv('RETENTION_HOURS', '24')) * 3600
MAX_JOBS = int(os.getenv('MAX_STORED_JOBS', '10'))
TRACKS = ('vocals', 'drums', 'bass', 'other', 'instrumental')
pool = ThreadPoolExecutor(max_workers=1)
active = set()


def save(folder, **values):
    target = folder / 'status.json'
    temp = folder / 'status.tmp'
    temp.write_text(json.dumps(values))
    temp.replace(target)


def command(args, timeout=120):
    return subprocess.run(args, check=True, capture_output=True, timeout=timeout)


def process(folder, source):
    try:
        save(folder, status='processing', message='Separando con Demucs. Puede tardar varios minutos.')
        probe = command(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(source)])
        duration = float(json.loads(probe.stdout)['format']['duration'])
        if not 0 < duration <= MAX_SECONDS:
            raise ValueError('La canción supera el límite de duración o no es válida.')
        normalized = folder / 'input.wav'
        command(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-t', str(MAX_SECONDS), '-ac', '2', '-ar', '44100', str(normalized)])
        command([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '-d', os.getenv('DEMUCS_DEVICE', 'cpu'), '--shifts', '1', '-j', '1', '--out', str(folder / 'separated'), str(normalized)], timeout=int(os.getenv('PROCESS_TIMEOUT_SECONDS', '3600')))
        stems = folder / 'separated' / 'htdemucs' / 'input'
        for name in TRACKS[:4]:
            shutil.move(str(stems / (name + '.wav')), folder / (name + '.wav'))
        command(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(folder / 'drums.wav'), '-i', str(folder / 'bass.wav'), '-i', str(folder / 'other.wav'), '-filter_complex', 'amix=inputs=3:normalize=0', '-c:a', 'pcm_s16le', str(folder / 'instrumental.wav')])
        save(folder, status='ready', duration=duration, tracks=list(TRACKS), message='Pistas listas')
    except Exception as exc:
        logging.getLogger(__name__).exception("Audio processing failed for job %s", folder.name)
        # Never expose subprocess logs or server paths to clients.
        message = str(exc) if isinstance(exc, ValueError) else 'No se pudo procesar el audio. Verificá el archivo, los modelos y los recursos del servidor.'
        save(folder, status='error', message=message)
    finally:
        source.unlink(missing_ok=True)
        (folder / 'input.wav').unlink(missing_ok=True)
        shutil.rmtree(folder / 'separated', ignore_errors=True)
        active.discard(folder.name)


def cleanup():
    for folder in DATA.iterdir():
        if folder.is_dir() and folder.name not in active and time.time() - folder.stat().st_mtime > TTL:
            shutil.rmtree(folder, ignore_errors=True)


@asynccontextmanager
async def lifespan(app):
    for folder in DATA.iterdir():
        status = folder / 'status.json'
        if status.exists():
            try:
                if json.loads(status.read_text())['status'] in ('queued', 'processing'):
                    save(folder, status='error', message='El servidor se reinició. Volvé a cargar el archivo.')
            except (ValueError, KeyError):
                pass
    async def reap():
        while True:
            cleanup()
            await asyncio.sleep(60)
    task = asyncio.create_task(reap())
    yield
    task.cancel()

app = FastAPI(title='Música Studio AI', lifespan=lifespan)

@app.get('/api/health')
def health():
    return {'status': 'ok', 'engine': 'demucs', 'max_upload_mb': MAX_BYTES // 1024 // 1024, 'max_duration_seconds': MAX_SECONDS}

@app.post('/api/jobs', status_code=202)
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.mp3', '.wav', '.m4a'):
        raise HTTPException(415, 'Elegí un archivo MP3, WAV o M4A.')
    cleanup()
    if len(list(DATA.iterdir())) >= MAX_JOBS or len(active) >= 3:
        raise HTTPException(429, 'El servidor está ocupado. Intentá más tarde.')
    job = secrets.token_urlsafe(24)
    folder = DATA / job
    folder.mkdir()
    active.add(job)
    source = folder / ('upload' + suffix)
    try:
        size = 0
        with source.open('wb') as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'El archivo supera el tamaño permitido.')
                stream.write(chunk)
        if not size:
            raise HTTPException(400, 'El archivo está vacío.')
        save(folder, status='queued', message='En cola de procesamiento')
        pool.submit(process, folder, source)
    except BaseException:
        active.discard(job)
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await file.close()
    return {'id': job}


def job_folder(job):
    if not job or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in job):
        raise HTTPException(404)
    folder = DATA / job
    if not (folder / 'status.json').exists():
        raise HTTPException(404, 'La sesión expiró o no existe.')
    return folder

@app.get('/api/jobs/{job}')
def status(job: str):
    return json.loads((job_folder(job) / 'status.json').read_text())

@app.get('/api/jobs/{job}/tracks/{track}')
def download(job: str, track: str):
    folder = job_folder(job)
    if track not in TRACKS or not (folder / (track + '.wav')).exists() or json.loads((folder / 'status.json').read_text())['status'] != 'ready':
        raise HTTPException(404)
    return FileResponse(folder / (track + '.wav'), media_type='audio/wav', filename=track + '.wav', headers={'Cache-Control': 'private, no-store'})

app.mount('/', StaticFiles(directory=Path(__file__).resolve().parent.parent / 'frontend', html=True), name='frontend')
