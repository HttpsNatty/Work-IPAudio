import os
import shutil
import tempfile
import uuid
import time
import logging
import subprocess
import wave
import asyncio
import math
from typing import Dict, Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from transformers import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IPAudio")

app = FastAPI(title="IPAudio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

whisper_pipeline = None
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ipa-whisper-base")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Simple in-memory job store. For production, replace with Redis or persistent store.
job_store: Dict[str, Dict[str, Any]] = {}
CHUNK_SECONDS = 30
CHUNK_CONCURRENCY = 2

@app.on_event("startup")
async def startup_event():
    global whisper_pipeline
    logger.info("Initializing IPAudio Backend...")
    
    if shutil.which("ffmpeg") is None:
        logger.error("FFmpeg not found in PATH! Required for audio conversion.")
        os._exit(1)
        
    logger.info(f"FFmpeg found. Loading Whisper model from {MODEL_PATH}...")
    try:
        whisper_pipeline = pipeline("automatic-speech-recognition", model=MODEL_PATH)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        os._exit(1)

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Accept file, create job and process asynchronously. Returns job_id for polling."""
    start_time = time.time()
    logger.info(f"Received file: {file.filename}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.error(f"File {file.filename} exceeds 10MB limit.")
        return JSONResponse(
            status_code=413,
            content={"success": False, "error": "File size exceeds 10MB limit."}
        )

    job_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    input_path = os.path.join(temp_dir, f"input_{job_id}_{safe_filename}")
    wav_path = os.path.join(temp_dir, f"output_{job_id}.wav")

    # initialize job
    job_store[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "transcription": None,
        "duration": None,
        "error": None,
    }

    # save uploaded file
    with open(input_path, "wb") as f:
        f.write(file_bytes)

    # start background processing task
    asyncio.create_task(process_job(job_id, input_path, wav_path, start_time, safe_filename))

    return {"success": True, "job_id": job_id}


async def process_job(job_id: str, input_path: str, wav_path: str, start_time: float, safe_filename: str):
    job = job_store.get(job_id)
    temp_dir = tempfile.gettempdir()
    trimmed_path = None
    try:
        job["status"] = "processing"
        job["progress"] = 5
        job["message"] = "Converting audio"

        # conversion
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "16000", wav_path]
        proc = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            stderr = proc.stderr.decode('utf-8', errors='ignore')
            job.update({"status": "error", "error": "FFmpeg conversion failed", "message": stderr, "progress": 0})
            return

        job.update({"progress": 30, "message": "Checking duration"})

        # check duration
        try:
            with wave.open(wav_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration_secs = frames / float(rate)
        except Exception:
            duration_secs = None

        transcription_input = wav_path
        if duration_secs is not None and duration_secs > 30:
            job.update({"progress": 50, "message": f"Trimming audio ({int(duration_secs)}s -> 30s)"})
            trimmed_path = os.path.join(temp_dir, f"trimmed_{job_id}.wav")
            cmd_trim = ["ffmpeg", "-y", "-i", wav_path, "-t", "30", trimmed_path]
            proc_trim = await asyncio.to_thread(subprocess.run, cmd_trim, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_trim.returncode == 0 and os.path.exists(trimmed_path):
                transcription_input = trimmed_path
            else:
                job["message"] = "Trim failed, proceeding with original"

        job.update({"progress": 60, "message": "Transcribing"})

        # If audio length is short or trimming occurred, still support chunking logic
        # determine number of chunks
        try:
            if duration_secs is None:
                # fallback: assume single chunk
                num_chunks = 1
            else:
                num_chunks = max(1, math.ceil(duration_secs / CHUNK_SECONDS))
        except Exception:
            num_chunks = 1

        chunk_paths = []
        # create chunk files using ffmpeg -ss / -t to avoid complex segment handling
        for i in range(num_chunks):
            start = i * CHUNK_SECONDS
            chunk_path = os.path.join(temp_dir, f"{job_id}_chunk_{i}.wav")
            # force WAV 16k mono output to ensure compatibility with readers
            cmd_chunk = [
                "ffmpeg", "-y", "-i", transcription_input, "-ss", str(start), "-t", str(CHUNK_SECONDS),
                "-ac", "1", "-ar", "16000", "-f", "wav", chunk_path
            ]
            proc_chunk = await asyncio.to_thread(subprocess.run, cmd_chunk, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_chunk.returncode == 0 and os.path.exists(chunk_path):
                try:
                    size = os.path.getsize(chunk_path)
                except Exception:
                    size = 0
                if size > 500:  # sanity check: small files are likely invalid
                    chunk_paths.append(chunk_path)
                else:
                    logger.warning(f"Chunk {chunk_path} created but too small ({size} bytes). Falling back to whole file.")
                    chunk_paths = [transcription_input]
                    break
            else:
                logger.warning(f"Failed to create chunk {chunk_path}: rc={getattr(proc_chunk, 'returncode', None)}")
                # if chunk creation failed, fallback to using the whole file as single chunk
                chunk_paths = [transcription_input]
                break

        # transcribe chunks with limited concurrency
        semaphore = asyncio.Semaphore(CHUNK_CONCURRENCY)

        async def transcribe_chunk(path, index):
            async with semaphore:
                # ensure file exists and is non-empty
                if not os.path.exists(path):
                    return index, None, f"Chunk file missing: {path}"
                try:
                    psize = os.path.getsize(path)
                except Exception:
                    psize = 0
                if psize < 500:
                    return index, None, f"Chunk file too small: {path} ({psize} bytes)"
                try:
                    result = await asyncio.to_thread(whisper_pipeline, path)
                    # extract text
                    text = ""
                    if isinstance(result, dict):
                        if "text" in result:
                            text = result.get("text", "").strip()
                        elif "chunks" in result:
                            text = " ".join([c.get("text", "").strip() for c in result.get("chunks", [])]).strip()
                    else:
                        text = str(result)
                    return index, text, None
                except Exception as e_trans:
                    msg = str(e_trans)
                    # attempt long-form per chunk
                    try:
                        result = await asyncio.to_thread(whisper_pipeline, path, return_timestamps=True)
                        text = result.get("text", "") if isinstance(result, dict) else str(result)
                        return index, text, None
                    except Exception as e2:
                        return index, None, msg + " | " + str(e2)

        tasks = [transcribe_chunk(p, idx) for idx, p in enumerate(chunk_paths)]
        completed = 0
        results = [None] * len(tasks)

        for coro in asyncio.as_completed(tasks):
            idx, text, err = await coro
            if err:
                job.update({"status": "error", "error": err, "message": "Chunk transcription failed", "progress": 0})
                # cancel remaining tasks
                # Note: remaining tasks will still run in background threads; we proceed to cleanup
                return
            results[idx] = text
            completed += 1
            # update progress proportionally (60..100)
            prog = 60 + int((completed / len(tasks)) * 40)
            job.update({"progress": prog, "message": f"Transcribed {completed}/{len(tasks)} chunks"})

        transcription = " ".join([r for r in results if r])

        duration = round(time.time() - start_time, 2)
        job.update({"status": "done", "progress": 100, "message": "Completed", "transcription": transcription, "duration": duration})
        logger.info(f"Job {job_id} completed in {duration}s")
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        job.update({"status": "error", "error": str(e), "message": "Internal error", "progress": 0})
    finally:
        # cleanup
        for p in [input_path, wav_path, trimmed_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = job_store.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"success": False, "error": "Job not found"})
    return {"success": True, "job": job}

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
