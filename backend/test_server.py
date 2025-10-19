#!/usr/bin/env python3
"""
Test version of the server that uses in-memory storage instead of MongoDB
For deployment testing purposes
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
import asyncio

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# In-memory storage for testing
videos_db = {}

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Models
class VideoInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_resolution: Optional[str] = None
    target_resolution: str = "1920x1080"
    status: str = "uploaded"  # uploaded, processing, completed, error
    error_message: Optional[str] = None
    upload_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_time: Optional[datetime] = None
    original_path: Optional[str] = None
    processed_path: Optional[str] = None

class VideoInfoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    filename: str
    original_resolution: Optional[str]
    target_resolution: str
    status: str
    error_message: Optional[str]
    upload_time: datetime
    processed_time: Optional[datetime]
    original_path: Optional[str]
    processed_path: Optional[str]

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "QuickScale 1080 Video Upscaler API", "status": "running"}

@api_router.post("/upload", response_model=VideoInfoResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file for processing"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Generate unique ID
    video_id = str(uuid.uuid4())

    # Read file content to simulate processing
    content = await file.read()

    # For testing, simulate metadata extraction
    # In a real implementation, this would use ffmpeg-python
    original_resolution = "1280x720"  # Mock resolution for test_720p.mp4

    video_info = VideoInfo(
        id=video_id,
        filename=file.filename,
        original_resolution=original_resolution,
        status="uploaded"
    )

    videos_db[video_id] = video_info

    return VideoInfoResponse(**video_info.model_dump())

@api_router.post("/process/{video_id}")
async def process_video(video_id: str):
    """Start video processing"""
    if video_id not in videos_db:
        raise HTTPException(status_code=404, detail="Video not found")

    video_info = videos_db[video_id]
    if video_info.status != "uploaded":
        raise HTTPException(status_code=400, detail="Video already processed or processing")

    # Simulate processing
    video_info.status = "processing"
    videos_db[video_id] = video_info

    # In a real implementation, this would start background processing
    # For testing, we'll just mark as completed immediately
    import asyncio
    asyncio.create_task(simulate_processing(video_id))

    return {"message": "Processing started", "video_id": video_id}

async def simulate_processing(video_id: str):
    """Simulate video processing for testing"""
    await asyncio.sleep(2)  # Simulate processing time

    if video_id in videos_db:
        video_info = videos_db[video_id]
        video_info.status = "completed"
        video_info.processed_time = datetime.now(timezone.utc)
        videos_db[video_id] = video_info

@api_router.get("/status/{video_id}", response_model=VideoInfoResponse)
async def get_video_status(video_id: str):
    """Get video processing status"""
    if video_id not in videos_db:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoInfoResponse(**videos_db[video_id].model_dump())

@api_router.get("/download/{video_id}")
async def download_video(video_id: str):
    """Download processed video"""
    if video_id not in videos_db:
        raise HTTPException(status_code=404, detail="Video not found")

    video_info = videos_db[video_id]
    if video_info.status != "completed":
        raise HTTPException(status_code=400, detail="Video not yet processed")

    # For testing, return a mock response
    return {"message": "Download would be available here", "video_id": video_id}

# Error handling
@api_router.get("/error-test")
async def test_error():
    """Test error handling"""
    raise HTTPException(status_code=500, detail="Test error")

# Include the router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)