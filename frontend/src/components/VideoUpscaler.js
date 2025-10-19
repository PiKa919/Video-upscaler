import React, { useState, useEffect } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function VideoUpscaler() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null);
  const [status, setStatus] = useState("idle"); // idle, uploading, processing, completed, error
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // Handle file selection
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith("video/")) {
      setSelectedFile(file);
      setStatus("idle");
      setError(null);
      setVideoInfo(null);
    } else {
      setError("Please select a valid video file");
    }
  };

  // Handle drag and drop
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("video/")) {
      setSelectedFile(file);
      setStatus("idle");
      setError(null);
      setVideoInfo(null);
    } else {
      setError("Please drop a valid video file");
    }
  };

  // Upload and process video
  const handleUploadAndProcess = async () => {
    if (!selectedFile) return;

    try {
      // Upload video
      setStatus("uploading");
      setProgress(30);
      setError(null);

      const formData = new FormData();
      formData.append("file", selectedFile);

      const uploadResponse = await axios.post(`${API}/upload`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const videoId = uploadResponse.data.id;
      setVideoInfo(uploadResponse.data);
      setProgress(50);

      // Start processing
      setStatus("processing");
      await axios.post(`${API}/process/${videoId}`);
      setProgress(60);

      // Poll for completion
      pollStatus(videoId);
    } catch (err) {
      console.error("Error:", err);
      setError(err.response?.data?.detail || "An error occurred");
      setStatus("error");
    }
  };

  // Poll for processing status
  const pollStatus = async (videoId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/status/${videoId}`);
        const data = response.data;

        if (data.status === "completed") {
          clearInterval(interval);
          setStatus("completed");
          setProgress(100);
          setVideoInfo(data);
        } else if (data.status === "error") {
          clearInterval(interval);
          setStatus("error");
          setError(data.error_message || "Processing failed");
        } else if (data.status === "processing") {
          // Gradually increase progress while processing
          setProgress((prev) => Math.min(prev + 2, 95));
        }
      } catch (err) {
        clearInterval(interval);
        setError("Failed to check processing status");
        setStatus("error");
      }
    }, 2000);
  };

  // Download processed video
  const handleDownload = async () => {
    if (videoInfo && status === "completed") {
      try {
        // Fetch the video file
        const response = await axios.get(`${API}/download/${videoInfo.id}`, {
          responseType: 'blob'
        });
        
        // Create a blob URL and trigger download
        const blob = new Blob([response.data], { type: 'video/mp4' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${videoInfo.filename.replace(/\.[^/.]+$/, '')}_1080p.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Download error:", err);
        setError("Failed to download video");
      }
    }
  };

  // Reset state
  const handleReset = () => {
    setSelectedFile(null);
    setVideoInfo(null);
    setStatus("idle");
    setProgress(0);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold text-white mb-3">
            QuickScale 1080
          </h1>
          <p className="text-slate-300 text-lg">
            Upscale your 720p videos to stunning 1080p quality
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {status === "idle" || status === "error" ? (
            <>
              {/* File Upload Area */}
              <div
                className={`border-3 border-dashed rounded-xl p-12 text-center transition-all ${
                  isDragging
                    ? "border-purple-500 bg-purple-50"
                    : "border-slate-300 bg-slate-50"
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="space-y-4">
                  <svg
                    className="mx-auto h-16 w-16 text-slate-400"
                    stroke="currentColor"
                    fill="none"
                    viewBox="0 0 48 48"
                  >
                    <path
                      d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div>
                    <label
                      htmlFor="file-upload"
                      className="cursor-pointer text-purple-600 hover:text-purple-700 font-semibold"
                    >
                      Click to upload
                    </label>
                    <span className="text-slate-600"> or drag and drop</span>
                  </div>
                  <p className="text-sm text-slate-500">
                    MP4, AVI, MKV, or any video format (720p recommended)
                  </p>
                  <input
                    id="file-upload"
                    type="file"
                    accept="video/*"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>
              </div>

              {/* Selected File Info */}
              {selectedFile && (
                <div className="mt-6 p-4 bg-slate-100 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <svg
                        className="h-8 w-8 text-purple-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                        />
                      </svg>
                      <div>
                        <p className="font-semibold text-slate-800">
                          {selectedFile.name}
                        </p>
                        <p className="text-sm text-slate-600">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={handleReset}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-700 text-sm">{error}</p>
                </div>
              )}

              {/* Start Button */}
              <button
                onClick={handleUploadAndProcess}
                disabled={!selectedFile}
                className="mt-6 w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-xl transition-colors text-lg shadow-lg"
              >
                Start Upscaling to 1080p
              </button>
            </>
          ) : status === "uploading" || status === "processing" ? (
            <>
              {/* Processing State */}
              <div className="text-center space-y-6">
                <div className="inline-block p-6 bg-purple-100 rounded-full">
                  <svg
                    className="h-16 w-16 text-purple-600 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-slate-800 mb-2">
                    {status === "uploading"
                      ? "Uploading Video..."
                      : "Upscaling to 1080p..."}
                  </h3>
                  <p className="text-slate-600">
                    {status === "uploading"
                      ? "Please wait while we upload your video"
                      : "Enhancing your video quality with bicubic algorithm"}
                  </p>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-purple-600 h-full transition-all duration-500 ease-out rounded-full"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-sm text-slate-600 font-semibold">
                  {progress}% Complete
                </p>
              </div>
            </>
          ) : status === "completed" ? (
            <>
              {/* Completion State */}
              <div className="text-center space-y-6">
                <div className="inline-block p-6 bg-green-100 rounded-full">
                  <svg
                    className="h-16 w-16 text-green-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-slate-800 mb-2">
                    Upscaling Complete!
                  </h3>
                  <p className="text-slate-600">
                    Your video has been successfully upscaled to 1080p
                  </p>
                </div>

                {videoInfo && (
                  <div className="bg-slate-100 rounded-lg p-4 text-left">
                    <h4 className="font-semibold text-slate-800 mb-2">
                      Video Details:
                    </h4>
                    <div className="space-y-1 text-sm text-slate-600">
                      <p>
                        <span className="font-medium">Original:</span>{" "}
                        {videoInfo.original_resolution}
                      </p>
                      <p>
                        <span className="font-medium">Upscaled:</span>{" "}
                        {videoInfo.target_resolution}
                      </p>
                      <p>
                        <span className="font-medium">Filename:</span>{" "}
                        {videoInfo.filename}
                      </p>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex space-x-4">
                  <button
                    onClick={handleDownload}
                    className="flex-1 bg-purple-600 hover:bg-purple-700 text-white font-semibold py-4 px-6 rounded-xl transition-colors shadow-lg"
                  >
                    Download 1080p Video
                  </button>
                  <button
                    onClick={handleReset}
                    className="flex-1 bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold py-4 px-6 rounded-xl transition-colors"
                  >
                    Upscale Another
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer Info */}
        <div className="mt-6 text-center text-slate-300 text-sm">
          <p>
            Preserves original framerate, codec, and audio quality • Bicubic
            upscaling algorithm
          </p>
        </div>
      </div>
    </div>
  );
}
