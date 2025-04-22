from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
import os
import uuid
import tempfile
import base64
import moviepy.editor as mp
from typing import Optional, Dict, Any, Union
import shutil

app = FastAPI(title="Video to Audio Extractor API")

class VideoRequest(BaseModel):
    url: Optional[HttpUrl] = None
    base64_data: Optional[str] = None
    filename: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com/video.mp4",
                "base64_data": None,
                "filename": "my_video.mp4"
            }
        }

class AudioResponse(BaseModel):
    download_url: str
    base64_data: Optional[str] = None
    mimetype: str
    filename: str
    
    class Config:
        schema_extra = {
            "example": {
                "download_url": "/download/audio_12345.mp3",
                "base64_data": "base64_encoded_string_here",
                "mimetype": "audio/mp3",
                "filename": "my_video.mp3"
            }
        }

# Ensure temp directory exists
TEMP_DIR = os.path.join(tempfile.gettempdir(), "audio_extractor")
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/extract-audio", response_model=AudioResponse)
async def extract_audio(video_request: VideoRequest = Body(...)):
    try:
        if not video_request.url and not video_request.base64_data:
            raise HTTPException(status_code=400, detail="Either URL or base64_data must be provided")
        
        # Generate unique filename if not provided
        original_filename = video_request.filename or "video"
        unique_id = str(uuid.uuid4())[:8]
        video_filename = f"{unique_id}_{original_filename}"
        video_path = os.path.join(TEMP_DIR, video_filename)
        
        # Process based on input type
        if video_request.url:
            # Download video from URL
            from urllib.request import urlretrieve
            urlretrieve(str(video_request.url), video_path)
        else:
            # Decode base64 data
            try:
                # Extract actual base64 data if it contains metadata
                if "," in video_request.base64_data:
                    base64_data = video_request.base64_data.split(",")[1]
                else:
                    base64_data = video_request.base64_data
                    
                video_data = base64.b64decode(base64_data)
                with open(video_path, "wb") as f:
                    f.write(video_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 data: {str(e)}")
        
        # Extract audio
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        audio_path = os.path.join(TEMP_DIR, audio_filename)
        
        try:
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path)
            video.close()
        except Exception as e:
            # Clean up files
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")
        
        # Clean up video file
        if os.path.exists(video_path):
            os.remove(video_path)
        
        # Create response
        download_url = f"/download/{audio_filename}"
        
        # Create base64 data for response
        with open(audio_path, "rb") as audio_file:
            audio_data = audio_file.read()
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
        
        return AudioResponse(
            download_url=download_url,
            base64_data=base64_audio,
            mimetype="audio/mp3",
            filename=audio_filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/download/{filename}")
async def download_audio(filename: str):
    file_path = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mp3",
        filename=filename
    )

# Cleanup task to remove old files
@app.on_event("startup")
async def startup_event():
    print("Starting cleanup task")

# Run a periodic cleanup task to remove files older than 1 hour
@app.on_event("shutdown")
async def shutdown_event():
    print("Cleaning up temporary files")
    try:
        shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
