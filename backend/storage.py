"""
Cloud storage abstraction for video files.
Supports local storage (development) and cloud storage (production).
"""

import os
import uuid
from pathlib import Path
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import NoCredentialsError
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

class CloudStorage:
    def __init__(self):
        self.storage_type = os.environ.get('STORAGE_TYPE', 'local').lower()

        if self.storage_type == 's3':
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                region_name=os.environ.get('AWS_REGION', 'us-east-1')
            )
            self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        elif self.storage_type == 'cloudinary':
            cloudinary.config(
                cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                api_key=os.environ.get('CLOUDINARY_API_KEY'),
                api_secret=os.environ.get('CLOUDINARY_API_SECRET')
            )
        elif self.storage_type == 'local':
            # Local storage for development
            self.upload_dir = Path(__file__).parent / "uploads"
            self.processed_dir = Path(__file__).parent / "processed"
            self.upload_dir.mkdir(exist_ok=True)
            self.processed_dir.mkdir(exist_ok=True)

    def generate_filename(self, original_filename: str, suffix: str = "") -> str:
        """Generate a unique filename"""
        file_id = str(uuid.uuid4())
        extension = Path(original_filename).suffix
        if suffix:
            return f"{file_id}_{suffix}{extension}"
        return f"{file_id}{extension}"

    async def upload_file(self, file_data: BinaryIO, filename: str, folder: str = "uploads") -> str:
        """Upload file and return the file URL/path"""
        if self.storage_type == 's3':
            return await self._upload_s3(file_data, filename, folder)
        elif self.storage_type == 'cloudinary':
            return await self._upload_cloudinary(file_data, filename, folder)
        else:  # local
            return self._upload_local(file_data, filename, folder)

    async def _upload_s3(self, file_data: BinaryIO, filename: str, folder: str) -> str:
        """Upload to AWS S3"""
        try:
            key = f"{folder}/{filename}"
            self.s3_client.upload_fileobj(file_data, self.bucket_name, key)

            # Generate public URL
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)['LocationConstraint']
            url = f"https://{self.bucket_name}.s3.{location}.amazonaws.com/{key}"
            return url
        except NoCredentialsError:
            raise Exception("AWS credentials not found")

    async def _upload_cloudinary(self, file_data: BinaryIO, filename: str, folder: str) -> str:
        """Upload to Cloudinary"""
        try:
            # Reset file pointer
            file_data.seek(0)

            result = cloudinary.uploader.upload(
                file_data,
                folder=folder,
                public_id=filename.replace(Path(filename).suffix, ''),
                resource_type="auto"
            )
            return result['secure_url']
        except Exception as e:
            raise Exception(f"Cloudinary upload failed: {str(e)}")

    def _upload_local(self, file_data: BinaryIO, filename: str, folder: str) -> str:
        """Upload to local filesystem"""
        if folder == "uploads":
            upload_path = self.upload_dir / filename
        else:
            upload_path = self.processed_dir / filename

        with open(upload_path, 'wb') as f:
            f.write(file_data.read())

        return str(upload_path)

    def get_file_url(self, file_path: str) -> str:
        """Get public URL for a file"""
        if self.storage_type == 's3':
            return self._get_s3_url(file_path)
        elif self.storage_type == 'cloudinary':
            return self._get_cloudinary_url(file_path)
        else:  # local
            return file_path  # Return local path

    def _get_s3_url(self, file_path: str) -> str:
        """Get S3 public URL"""
        location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)['LocationConstraint']
        return f"https://{self.bucket_name}.s3.{location}.amazonaws.com/{file_path}"

    def _get_cloudinary_url(self, file_path: str) -> str:
        """Get Cloudinary public URL"""
        # For Cloudinary, we assume file_path is already a full URL
        return file_path

    def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        try:
            if self.storage_type == 's3':
                key = file_path.split('/')[-1]  # Extract key from URL
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            elif self.storage_type == 'cloudinary':
                # Extract public_id from Cloudinary URL
                public_id = file_path.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(public_id)
            else:  # local
                Path(file_path).unlink(missing_ok=True)
            return True
        except Exception:
            return False

# Global storage instance
storage = CloudStorage()