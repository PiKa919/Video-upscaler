#!/usr/bin/env python3
"""
QuickScale 1080 Backend API Test Suite
Tests all backend endpoints for video upscaling functionality
"""

import requests
import json
import time
import os
import subprocess
from pathlib import Path
import sys

# Configuration
BASE_URL = "https://video-enhancer-17.preview.emergentagent.com/api"
TEST_VIDEO_PATH = "/app/test_720p.mp4"
TIMEOUT = 300  # 5 minutes timeout for processing

class VideoUpscalerTester:
    def __init__(self):
        self.session = requests.Session()
        self.video_id = None
        self.test_results = {
            "upload": False,
            "process": False,
            "status_polling": False,
            "download": False,
            "metadata_verification": False,
            "error_handling": False
        }
        
    def log(self, message, level="INFO"):
        """Log messages with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def test_api_health(self):
        """Test if API is accessible"""
        try:
            response = self.session.get(f"{BASE_URL}/")
            if response.status_code == 200:
                self.log("✅ API health check passed")
                return True
            else:
                self.log(f"❌ API health check failed: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ API health check failed: {e}")
            return False
    
    def test_video_upload(self):
        """Test POST /api/upload endpoint"""
        self.log("Testing video upload endpoint...")
        
        try:
            # Check if test video exists
            if not Path(TEST_VIDEO_PATH).exists():
                self.log(f"❌ Test video not found: {TEST_VIDEO_PATH}")
                return False
            
            # Upload video
            with open(TEST_VIDEO_PATH, 'rb') as f:
                files = {'file': ('test_720p.mp4', f, 'video/mp4')}
                response = self.session.post(f"{BASE_URL}/upload", files=files)
            
            if response.status_code != 200:
                self.log(f"❌ Upload failed: {response.status_code} - {response.text}")
                return False
            
            data = response.json()
            self.video_id = data.get('id')
            
            # Verify response structure
            required_fields = ['id', 'filename', 'original_resolution', 'status']
            for field in required_fields:
                if field not in data:
                    self.log(f"❌ Missing field in response: {field}")
                    return False
            
            # Verify values
            if data['original_resolution'] != '1280x720':
                self.log(f"❌ Incorrect resolution: expected 1280x720, got {data['original_resolution']}")
                return False
            
            if data['status'] != 'uploaded':
                self.log(f"❌ Incorrect status: expected 'uploaded', got {data['status']}")
                return False
            
            self.log(f"✅ Video uploaded successfully. ID: {self.video_id}")
            self.log(f"   Filename: {data['filename']}")
            self.log(f"   Resolution: {data['original_resolution']}")
            self.log(f"   Status: {data['status']}")
            
            self.test_results["upload"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Upload test failed: {e}")
            return False
    
    def test_video_processing(self):
        """Test POST /api/process/{video_id} endpoint"""
        if not self.video_id:
            self.log("❌ No video ID available for processing test")
            return False
        
        self.log("Testing video processing endpoint...")
        
        try:
            response = self.session.post(f"{BASE_URL}/process/{self.video_id}")
            
            if response.status_code != 200:
                self.log(f"❌ Processing failed: {response.status_code} - {response.text}")
                return False
            
            data = response.json()
            
            if 'message' not in data or 'video_id' not in data:
                self.log(f"❌ Invalid processing response: {data}")
                return False
            
            if data['video_id'] != self.video_id:
                self.log(f"❌ Video ID mismatch: expected {self.video_id}, got {data['video_id']}")
                return False
            
            self.log(f"✅ Processing started successfully")
            self.log(f"   Message: {data['message']}")
            
            self.test_results["process"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Processing test failed: {e}")
            return False
    
    def test_status_polling(self):
        """Test GET /api/status/{video_id} endpoint and wait for completion"""
        if not self.video_id:
            self.log("❌ No video ID available for status test")
            return False
        
        self.log("Testing status polling endpoint...")
        
        try:
            start_time = time.time()
            status_transitions = []
            
            while time.time() - start_time < TIMEOUT:
                response = self.session.get(f"{BASE_URL}/status/{self.video_id}")
                
                if response.status_code != 200:
                    self.log(f"❌ Status check failed: {response.status_code} - {response.text}")
                    return False
                
                data = response.json()
                current_status = data.get('status')
                
                # Log status transitions
                if not status_transitions or status_transitions[-1] != current_status:
                    status_transitions.append(current_status)
                    self.log(f"   Status: {current_status}")
                
                if current_status == 'completed':
                    self.log(f"✅ Processing completed successfully")
                    self.log(f"   Status transitions: {' -> '.join(status_transitions)}")
                    self.log(f"   Processing time: {time.time() - start_time:.1f} seconds")
                    
                    # Verify final response structure
                    required_fields = ['id', 'filename', 'original_resolution', 'target_resolution', 'status']
                    for field in required_fields:
                        if field not in data:
                            self.log(f"❌ Missing field in status response: {field}")
                            return False
                    
                    if data['target_resolution'] != '1920x1080':
                        self.log(f"❌ Incorrect target resolution: {data['target_resolution']}")
                        return False
                    
                    self.test_results["status_polling"] = True
                    return True
                
                elif current_status == 'error':
                    error_msg = data.get('error_message', 'Unknown error')
                    self.log(f"❌ Processing failed with error: {error_msg}")
                    return False
                
                # Wait before next poll
                time.sleep(2)
            
            self.log(f"❌ Processing timeout after {TIMEOUT} seconds")
            return False
            
        except Exception as e:
            self.log(f"❌ Status polling test failed: {e}")
            return False
    
    def test_video_download(self):
        """Test GET /api/download/{video_id} endpoint"""
        if not self.video_id:
            self.log("❌ No video ID available for download test")
            return False
        
        self.log("Testing video download endpoint...")
        
        try:
            response = self.session.get(f"{BASE_URL}/download/{self.video_id}")
            
            if response.status_code != 200:
                self.log(f"❌ Download failed: {response.status_code} - {response.text}")
                return False
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'video' not in content_type:
                self.log(f"❌ Invalid content type: {content_type}")
                return False
            
            # Save downloaded file
            download_path = "/app/downloaded_1080p.mp4"
            with open(download_path, 'wb') as f:
                f.write(response.content)
            
            # Verify file size
            file_size = len(response.content)
            if file_size < 1000:  # Should be larger than 1KB
                self.log(f"❌ Downloaded file too small: {file_size} bytes")
                return False
            
            self.log(f"✅ Video downloaded successfully")
            self.log(f"   File size: {file_size} bytes")
            self.log(f"   Content type: {content_type}")
            
            self.test_results["download"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Download test failed: {e}")
            return False
    
    def test_metadata_verification(self):
        """Verify video metadata using ffmpeg"""
        self.log("Testing metadata verification...")
        
        try:
            download_path = "/app/downloaded_1080p.mp4"
            if not Path(download_path).exists():
                self.log("❌ Downloaded file not found for metadata verification")
                return False
            
            # Get video info using ffprobe
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_streams', download_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.log(f"❌ ffprobe failed: {result.stderr}")
                return False
            
            data = json.loads(result.stdout)
            video_stream = None
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                self.log("❌ No video stream found in downloaded file")
                return False
            
            # Verify resolution
            width = video_stream.get('width')
            height = video_stream.get('height')
            
            if width != 1920 or height != 1080:
                self.log(f"❌ Incorrect output resolution: {width}x{height}, expected 1920x1080")
                return False
            
            # Verify codec
            codec = video_stream.get('codec_name')
            if codec != 'h264':
                self.log(f"❌ Incorrect codec: {codec}, expected h264")
                return False
            
            self.log(f"✅ Metadata verification passed")
            self.log(f"   Resolution: {width}x{height}")
            self.log(f"   Codec: {codec}")
            
            self.test_results["metadata_verification"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Metadata verification failed: {e}")
            return False
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        self.log("Testing error handling...")
        
        try:
            # Test 1: Process non-existent video
            fake_id = "non-existent-id"
            response = self.session.post(f"{BASE_URL}/process/{fake_id}")
            
            if response.status_code != 404:
                self.log(f"❌ Expected 404 for non-existent video, got {response.status_code}")
                return False
            
            # Test 2: Download non-existent video
            response = self.session.get(f"{BASE_URL}/download/{fake_id}")
            
            if response.status_code != 404:
                self.log(f"❌ Expected 404 for non-existent download, got {response.status_code}")
                return False
            
            # Test 3: Status of non-existent video
            response = self.session.get(f"{BASE_URL}/status/{fake_id}")
            
            if response.status_code != 404:
                self.log(f"❌ Expected 404 for non-existent status, got {response.status_code}")
                return False
            
            self.log(f"✅ Error handling tests passed")
            self.test_results["error_handling"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Error handling test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("Starting QuickScale 1080 Backend API Tests")
        self.log("=" * 50)
        
        # Test API health first
        if not self.test_api_health():
            self.log("❌ API health check failed, aborting tests")
            return False
        
        # Run tests in sequence
        tests = [
            ("Video Upload", self.test_video_upload),
            ("Video Processing", self.test_video_processing),
            ("Status Polling", self.test_status_polling),
            ("Video Download", self.test_video_download),
            ("Metadata Verification", self.test_metadata_verification),
            ("Error Handling", self.test_error_handling)
        ]
        
        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            success = test_func()
            if not success:
                self.log(f"❌ {test_name} failed, continuing with remaining tests...")
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        return all(self.test_results.values())
    
    def print_summary(self):
        """Print test results summary"""
        self.log("\n" + "=" * 50)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 50)
        
        passed = sum(self.test_results.values())
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{test_name.replace('_', ' ').title()}: {status}")
        
        self.log(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            self.log("🎉 All tests passed! Backend API is working correctly.")
        else:
            self.log(f"⚠️  {total - passed} test(s) failed. Please check the logs above.")

def main():
    """Main test execution"""
    tester = VideoUpscalerTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()