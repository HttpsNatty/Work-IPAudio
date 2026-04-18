import os
import shutil
import tempfile
import uuid
import time
import logging
import subprocess

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
    start_time = time.time()
    logger.info(f"Received file: {file.filename}")
    
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.error(f"File {file.filename} exceeds 10MB limit.")
        return JSONResponse(
            status_code=413, 
            content={"success": False, "transcription": "", "error": "File size exceeds 10MB limit.", "duration": 0}
        )
        
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    input_path = os.path.join(temp_dir, f"input_{session_id}_{safe_filename}")
    wav_path = os.path.join(temp_dir, f"output_{session_id}.wav")
    
    try:
        with open(input_path, "wb") as f:
            f.write(file_bytes)
            
        logger.info(f"Converting audio {file.filename} to mono 16kHz WAV...")
        # conversion to mono (-ac 1), 16kHz (-ar 16000)
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "16000", wav_path]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if process.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {process.stderr.decode('utf-8', errors='ignore')}")
            return JSONResponse(
                status_code=400, 
                content={"success": False, "transcription": "", "error": "Invalid audio file or format not supported.", "duration": 0}
            )
            
        logger.info("Starting transcription...")
        transcription_result = whisper_pipeline(wav_path)
        transcription = transcription_result.get("text", "").strip()
        
        duration = round(time.time() - start_time, 2)
        logger.info(f"Transcription successful in {duration}s")
        
        return {"success": True, "transcription": transcription, "duration": duration, "error": None}
        
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        return JSONResponse(
            status_code=500, 
            content={"success": False, "transcription": "", "error": "Internal server error during processing.", "duration": 0}
        )
        
    finally:
        for p in [input_path, wav_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"Cleaned up temp file: {p}")
                except Exception as e:
                    logger.error(f"Failed to clean up {p}: {e}")

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
