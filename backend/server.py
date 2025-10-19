from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import ffmpeg
import aiofiles
import asyncio
from PIL import Image
import json
import shutil


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create directories for video storage
UPLOAD_DIR = ROOT_DIR / "uploads"
PROCESSED_DIR = ROOT_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


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
    id: str
    filename: str
    original_resolution: Optional[str] = None
    target_resolution: str
    status: str
    error_message: Optional[str] = None
    upload_time: datetime
    processed_time: Optional[datetime] = None


# Helper function to get video metadata
def get_video_info(video_path: str) -> dict:
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        
        return {
            'width': int(video_info['width']),
            'height': int(video_info['height']),
            'codec': video_info['codec_name'],
            'fps': eval(video_info.get('r_frame_rate', '30/1')),
            'duration': float(probe['format'].get('duration', 0))
        }
    except Exception as e:
        logging.error(f"Error getting video info: {e}")
        return {}


# Helper function to upscale video
async def upscale_video(input_path: str, output_path: str, video_id: str) -> bool:
    try:
        # Get input video info
        video_info = get_video_info(input_path)
        
        # Use bicubic scaling algorithm for upscaling
        # Preserve codec, audio, and other metadata
        stream = ffmpeg.input(input_path)
        
        # Scale video to 1920x1080 using bicubic algorithm
        video = stream.video.filter('scale', 1920, 1080, flags='bicubic')
        
        # Copy audio without re-encoding
        audio = stream.audio
        
        # Output with same codec and settings
        output = ffmpeg.output(
            video, 
            audio, 
            output_path,
            vcodec='libx264',  # Use H.264 codec
            acodec='copy',  # Copy audio without re-encoding
            preset='medium',  # Balance between speed and quality
            crf=18  # High quality setting
        )
        
        # Run FFmpeg
        await asyncio.to_thread(output.overwrite_output().run)
        
        # Update database
        await db.videos.update_one(
            {"id": video_id},
            {
                "$set": {
                    "status": "completed",
                    "processed_time": datetime.now(timezone.utc).isoformat(),
                    "processed_path": output_path
                }
            }
        )
        
        return True
    except Exception as e:
        logging.error(f"Error upscaling video: {e}")
        # Update database with error
        await db.videos.update_one(
            {"id": video_id},
            {
                "$set": {
                    "status": "error",
                    "error_message": str(e)
                }
            }
        )
        return False


# Routes
@api_router.get("/")
async def root():
    return {"message": "QuickScale 1080 API"}


@api_router.post("/upload", response_model=VideoInfoResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file"""
    try:
        # Generate unique ID
        video_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        
        # Save uploaded file
        upload_path = UPLOAD_DIR / f"{video_id}{file_extension}"
        
        async with aiofiles.open(upload_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Get video information
        video_info = get_video_info(str(upload_path))
        resolution = f"{video_info.get('width', 0)}x{video_info.get('height', 0)}" if video_info else None
        
        # Create video record
        video_record = VideoInfo(
            id=video_id,
            filename=file.filename,
            original_resolution=resolution,
            original_path=str(upload_path),
            status="uploaded"
        )
        
        # Save to database
        doc = video_record.model_dump()
        doc['upload_time'] = doc['upload_time'].isoformat()
        await db.videos.insert_one(doc)
        
        return VideoInfoResponse(**video_record.model_dump())
        
    except Exception as e:
        logging.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/process/{video_id}")
async def process_video(video_id: str):
    """Start processing (upscaling) a video"""
    try:
        # Get video from database
        video = await db.videos.find_one({"id": video_id}, {"_id": 0})
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        if video['status'] != 'uploaded':
            raise HTTPException(status_code=400, detail="Video already processed or processing")
        
        # Update status to processing
        await db.videos.update_one(
            {"id": video_id},
            {"$set": {"status": "processing"}}
        )
        
        # Get paths
        input_path = video['original_path']
        file_extension = Path(input_path).suffix
        output_path = str(PROCESSED_DIR / f"{video_id}_1080p{file_extension}")
        
        # Start upscaling in background
        asyncio.create_task(upscale_video(input_path, output_path, video_id))
        
        return {"message": "Processing started", "video_id": video_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error processing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/status/{video_id}", response_model=VideoInfoResponse)
async def get_video_status(video_id: str):
    """Get the status of a video"""
    try:
        video = await db.videos.find_one({"id": video_id}, {"_id": 0})
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Convert ISO string timestamps back to datetime objects
        if isinstance(video.get('upload_time'), str):
            video['upload_time'] = datetime.fromisoformat(video['upload_time'])
        if video.get('processed_time') and isinstance(video['processed_time'], str):
            video['processed_time'] = datetime.fromisoformat(video['processed_time'])
        
        return VideoInfoResponse(**video)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting video status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/download/{video_id}")
async def download_video(video_id: str):
    """Download the processed video"""
    try:
        video = await db.videos.find_one({"id": video_id}, {"_id": 0})
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        if video['status'] != 'completed':
            raise HTTPException(status_code=400, detail="Video not ready for download")
        
        processed_path = video.get('processed_path')
        if not processed_path or not Path(processed_path).exists():
            raise HTTPException(status_code=404, detail="Processed file not found")
        
        # Create download filename
        original_name = Path(video['filename']).stem
        extension = Path(processed_path).suffix
        download_name = f"{original_name}_1080p{extension}"
        
        return FileResponse(
            processed_path,
            media_type="video/mp4",
            filename=download_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/videos", response_model=List[VideoInfoResponse])
async def list_videos():
    """List all videos"""
    try:
        videos = await db.videos.find({}, {"_id": 0}).sort("upload_time", -1).to_list(100)
        
        # Convert ISO string timestamps back to datetime objects
        for video in videos:
            if isinstance(video.get('upload_time'), str):
                video['upload_time'] = datetime.fromisoformat(video['upload_time'])
            if video.get('processed_time') and isinstance(video['processed_time'], str):
                video['processed_time'] = datetime.fromisoformat(video['processed_time'])
        
        return [VideoInfoResponse(**video) for video in videos]
        
    except Exception as e:
        logging.error(f"Error listing videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()