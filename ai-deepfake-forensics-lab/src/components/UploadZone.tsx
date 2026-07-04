/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useRef, useState } from 'react';
import { Upload, Link as LinkIcon, AlertTriangle } from 'lucide-react';

interface UploadZoneProps {
  onFileSelect: (file: File | { url: string; type: 'image' | 'video'; name: string }) => void;
  isLoading: boolean;
}

export default function UploadZone({ onFileSelect, isLoading }: UploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true);
    } else if (e.type === 'dragleave') {
      setIsDragActive(false);
    }
  };

  const processFile = (file: File) => {
    setErrorMsg('');
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');

    if (!isImage && !isVideo) {
      setErrorMsg('Unsupported file format. Please upload an image (PNG, JPG, WEBP) or a video (MP4, WEBM).');
      return;
    }
    onFileSelect(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!urlInput.trim()) return;

    const trimmedUrl = urlInput.trim();
    // Simple heuristic to detect if URL is likely image or video
    const extension = trimmedUrl.split('?')[0].split('.').pop()?.toLowerCase();
    const isVideo = extension ? ['mp4', 'webm', 'ogg', 'mov'].includes(extension) : false;

    onFileSelect({
      url: trimmedUrl,
      type: isVideo ? 'video' : 'image',
      name: trimmedUrl.split('/').pop() || 'Remote Asset'
    });
    setUrlInput('');
  };

  return (
    <div className="bg-gray-950 rounded-2xl border border-gray-900 p-6 shadow-xl transition-all duration-300">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-white">
          Upload Digital Evidence
        </h3>
        <p className="text-xs text-gray-450 mt-0.5">
          Provide an image or high-definition video file to initiate forensic analysis.
        </p>
      </div>

      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isLoading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 ${
          isDragActive
            ? 'border-cyan-500 bg-cyan-950/20'
            : 'border-gray-800 hover:border-cyan-700/60 bg-gray-900/10'
        } ${isLoading ? 'opacity-50 pointer-events-none' : ''}`}
        id="drag-drop-area"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,video/*"
          className="hidden"
          onChange={handleFileChange}
          disabled={isLoading}
        />

        <div className="w-12 h-12 rounded-full bg-cyan-950/40 text-cyan-400 flex items-center justify-center mb-3 border border-cyan-900/35">
          <Upload className="w-5 h-5 animate-bounce" />
        </div>

        <p className="text-sm font-medium text-gray-200">
          Drag and drop media here, or <span className="text-cyan-400 hover:underline">browse files</span>
        </p>
        <p className="text-xs text-gray-500 mt-1">
          Supports JPG, PNG, WEBP, MP4, WEBM (up to 50MB)
        </p>
      </div>

      <div className="relative flex items-center justify-center my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-900"></div>
        </div>
        <span className="relative px-3 bg-gray-950 text-xs text-gray-500 uppercase tracking-widest font-mono">
          Or analyze via Link
        </span>
      </div>

      <form onSubmit={handleUrlSubmit} className="flex gap-2">
        <div className="relative flex-grow">
          <LinkIcon className="absolute left-3 top-3 w-4 h-4 text-gray-500" />
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Paste public image or video URL..."
            className="w-full pl-9 pr-3 py-2.5 text-xs bg-gray-900 rounded-xl border border-gray-805 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-505 focus:ring-1 focus:ring-cyan-500 transition-all duration-300"
            disabled={isLoading}
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-bold uppercase transition duration-200 shadow-lg disabled:opacity-40"
          disabled={isLoading || !urlInput.trim()}
        >
          Submit
        </button>
      </form>

      {errorMsg && (
        <div className="mt-3 flex items-start gap-2.5 p-3 rounded-xl bg-rose-950/20 border border-rose-900/45 text-rose-400 text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );
}
