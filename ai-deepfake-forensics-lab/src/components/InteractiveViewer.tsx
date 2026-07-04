/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Eye, ShieldAlert, Zap, Layers, RefreshCw, Sparkles } from 'lucide-react';
import { SampleMedia, AnalysisOverlay } from '../types';

interface InteractiveViewerProps {
  media: SampleMedia | null;
  isScanning: boolean;
  scanProgress: number;
  onReScan: () => void;
}

export default function InteractiveViewer({ media, isScanning, scanProgress, onReScan }: InteractiveViewerProps) {
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showAnomalies, setShowAnomalies] = useState(true);
  const [showLighting, setShowLighting] = useState(false);
  const [useELA, setUseELA] = useState(false);
  const [hoveredOverlay, setHoveredOverlay] = useState<AnalysisOverlay | null>(null);

  if (!media) {
    return (
      <div className="bg-gray-100 dark:bg-gray-950 rounded-2xl border border-gray-200 dark:border-gray-850 aspect-video flex flex-col items-center justify-center p-6 text-center text-gray-400 dark:text-gray-500">
        <Sparkles className="w-8 h-8 mb-2 animate-pulse text-gray-300 dark:text-gray-700" />
        <p className="text-sm font-medium">No media loaded for analysis</p>
        <p className="text-xs max-w-sm mt-1">
          Select one of the sample cases below or upload your own file to start the forensic engine.
        </p>
      </div>
    );
  }

  // Generate face mesh lines automatically based on actual metadata coordinates
  const renderFaceMesh = () => {
    if (!showLandmarks || useELA || isScanning) return null;
    
    // Find custom landmark points within the overlays
    const landmarks = media.overlays.filter(o => o.type === 'landmark');
    if (landmarks.length < 2) return null;

    return (
      <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
        {/* Draw facial wireframe lines between key coordinates to simulate a mesh */}
        {landmarks.map((l1, i) => 
          landmarks.slice(i + 1).map((l2, j) => {
            // Only connect logical coordinates within proximity to avoid cluttered lines
            const dx = Math.abs(l1.x - l2.x);
            const dy = Math.abs(l1.y - l2.y);
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 40) {
              return (
                <line
                  key={`${l1.id}-${l2.id}`}
                  x1={`${l1.x}%`}
                  y1={`${l1.y}%`}
                  x2={`${l2.x}%`}
                  y2={`${l2.y}%`}
                  className="stroke-sky-400/40 dark:stroke-sky-400/30 stroke-[1]"
                  strokeDasharray="2 3"
                />
              );
            }
            return null;
          })
        )}
      </svg>
    );
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm flex flex-col transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold uppercase tracking-wider bg-sky-100 dark:bg-sky-950/50 text-sky-700 dark:text-sky-450 px-2 py-0.5 rounded-md">
            Digital Exhibit
          </span>
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-250 truncate max-w-[200px] md:max-w-[300px]">
            {media.title}
          </span>
        </div>

        {!isScanning && (
          <button
            onClick={onReScan}
            className="flex items-center space-x-1.5 text-xs text-gray-500 hover:text-sky-600 dark:hover:text-sky-400 font-medium transition"
            id="re-scan-btn"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Re-run Scan</span>
          </button>
        )}
      </div>

      <div className="relative overflow-hidden rounded-xl bg-black aspect-video flex items-center justify-center border border-gray-150 dark:border-gray-800">
        {/* Main Media Renders */}
        {media.type === 'video' ? (
          <img
            src={media.url}
            alt={media.title}
            referrerPolicy="no-referrer"
            className={`w-full h-full object-cover transition-all duration-300 ${
              useELA ? 'filter brightness-50 contrast-200 saturate-[4] hue-rotate-[210deg] invert' : ''
            }`}
          />
        ) : (
          <img
            src={media.url}
            alt={media.title}
            referrerPolicy="no-referrer"
            className={`w-full h-full object-cover transition-all duration-300 ${
              useELA ? 'filter brightness-50 contrast-200 saturate-[4] hue-rotate-[210deg] invert' : ''
            }`}
          />
        )}

        {/* ELA Simulation Backdrop Grid */}
        {useELA && !isScanning && (
          <div className="absolute inset-0 bg-radial-gradient from-transparent to-black/90 pointer-events-none mix-blend-overlay"></div>
        )}

        {/* Real-time Scanning animation line */}
        {isScanning && (
          <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center">
            {/* The scanning laser sweep bar */}
            <div 
              className="absolute left-0 right-0 h-1.5 bg-gradient-to-r from-transparent via-sky-400 to-transparent shadow-[0_0_15px_#38bdf8]"
              style={{
                top: `${(Math.sin((scanProgress / 100) * Math.PI * 4) + 1) * 50}%`,
                transition: 'top 0.1s ease-out'
              }}
            />
            <div className="bg-black/80 backdrop-blur-md border border-sky-500/30 rounded-xl px-5 py-4 text-center max-w-sm">
              <div className="flex justify-center mb-2">
                <RefreshCw className="w-5 h-5 text-sky-400 animate-spin" />
              </div>
              <p className="text-xs font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Forensic Scanner Engaged
              </p>
              <div className="w-48 bg-gray-800 h-1.5 rounded-full mt-2 overflow-hidden mx-auto">
                <div 
                  className="bg-sky-400 h-full rounded-full transition-all duration-100" 
                  style={{ width: `${scanProgress}%` }}
                />
              </div>
              <p className="text-[10px] font-mono text-gray-400 mt-1.5">
                Isolating Pixel Frequencies: {scanProgress}%
              </p>
            </div>
          </div>
        )}

        {/* Interactive Overlays on top of the image */}
        {!isScanning && (
          <>
            {renderFaceMesh()}

            {media.overlays.map((overlay) => {
              if (overlay.type === 'landmark' && !showLandmarks) return null;
              if (overlay.type === 'anomaly' && !showAnomalies) return null;
              if (overlay.type === 'light_vector' && !showLighting) return null;
              if (useELA) return null; // Hide markers during ELA to emphasize noise matrix

              const isAnomaly = overlay.type === 'anomaly';
              const isLight = overlay.type === 'light_vector';

              return (
                <div
                  key={overlay.id}
                  className="absolute"
                  style={{ left: `${overlay.x}%`, top: `${overlay.y}%` }}
                  onMouseEnter={() => setHoveredOverlay(overlay)}
                  onMouseLeave={() => setHoveredOverlay(null)}
                >
                  {isAnomaly ? (
                    // Red bounding warning brackets for simulated anomalies
                    <div 
                      className="relative border-2 border-dashed border-rose-500/80 bg-rose-500/10 rounded cursor-help animate-pulse group"
                      style={{
                        width: `${(overlay.w || 15) * 4}px`,
                        height: `${(overlay.h || 12) * 4}px`,
                        transform: 'translate(-50%, -50%)'
                      }}
                      id={`anomaly-box-${overlay.id}`}
                    >
                      <span className="absolute -top-5 left-0 bg-rose-600 text-[9px] text-white font-mono font-bold px-1 py-0.5 rounded flex items-center gap-1 shadow">
                        <ShieldAlert className="w-2.5 h-2.5" />
                        ANOMALY
                      </span>
                    </div>
                  ) : isLight ? (
                    // Lighting direction vector helper arrow
                    <div 
                      className="relative flex items-center justify-center cursor-help group"
                      style={{ transform: 'translate(-50%, -50%)' }}
                      id={`light-vector-${overlay.id}`}
                    >
                      <div className="w-8 h-8 rounded-full border border-teal-500 bg-teal-500/20 flex items-center justify-center animate-spin-slow">
                        <Zap className="w-3.5 h-3.5 text-teal-400" />
                      </div>
                      <div className="absolute top-8 bg-teal-900 border border-teal-500 text-[9px] text-teal-350 font-mono px-1 py-0.5 rounded shadow whitespace-nowrap">
                        LIGHT VECTOR
                      </div>
                    </div>
                  ) : (
                    // Biometric landmarks (glowing small core points)
                    <div 
                      className="relative w-2.5 h-2.5 bg-sky-400 border border-white rounded-full cursor-help shadow-[0_0_8px_#38bdf8] hover:scale-135 transition-all duration-150"
                      style={{ transform: 'translate(-50%, -50%)' }}
                      id={`landmark-node-${overlay.id}`}
                    >
                      <div className="absolute inset-0 bg-sky-400 rounded-full animate-ping opacity-60"></div>
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}

        {/* Hovered overlay description tooltip */}
        {hoveredOverlay && !isScanning && !useELA && (
          <div className="absolute bottom-3 left-3 right-3 bg-gray-950/95 border border-sky-500/30 p-2.5 rounded-lg text-white text-xs font-sans shadow-lg flex items-start gap-2.5 z-20">
            <div className={`mt-0.5 p-1 rounded ${
              hoveredOverlay.type === 'anomaly' 
                ? 'bg-rose-500/20 text-rose-400' 
                : hoveredOverlay.type === 'light_vector'
                ? 'bg-teal-500/20 text-teal-400'
                : 'bg-sky-500/20 text-sky-450'
            }`}>
              {hoveredOverlay.type === 'anomaly' ? (
                <ShieldAlert className="w-3.5 h-3.5" />
              ) : hoveredOverlay.type === 'light_vector' ? (
                <Zap className="w-3.5 h-3.5" />
              ) : (
                <Eye className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <div className="font-semibold tracking-wide text-gray-200">
                {hoveredOverlay.label}
              </div>
              <div className="text-gray-400 text-[11px] mt-0.5 leading-relaxed">
                {hoveredOverlay.description}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Forensic Lens Controls */}
      <div className="mt-4 border-t border-gray-100 dark:border-gray-800 pt-4">
        <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2.5 uppercase tracking-wider flex items-center gap-1">
          <Layers className="w-3.5 h-3.5 text-gray-400" />
          Interactive Diagnostics
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {/* Landmark layers toggle */}
          <button
            onClick={() => { setShowLandmarks(!showLandmarks); setUseELA(false); }}
            disabled={isScanning}
            className={`flex items-center space-x-2 px-3 py-2 rounded-xl text-left border text-xs font-medium transition ${
              showLandmarks && !useELA
                ? 'bg-sky-50 dark:bg-sky-950/30 border-sky-200 dark:border-sky-900/40 text-sky-700 dark:text-sky-300'
                : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-850 hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400'
            }`}
            id="toggle-landmarks-btn"
          >
            <div className={`w-2 h-2 rounded-full ${showLandmarks && !useELA ? 'bg-sky-500' : 'bg-gray-400'}`}></div>
            <span>Facial Landmarks</span>
          </button>

          {/* Anomaly box toggle */}
          <button
            onClick={() => { setShowAnomalies(!showAnomalies); setUseELA(false); }}
            disabled={isScanning}
            className={`flex items-center space-x-2 px-3 py-2 rounded-xl text-left border text-xs font-medium transition ${
              showAnomalies && !useELA
                ? 'bg-rose-50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-950/30 text-rose-700 dark:text-rose-400'
                : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-850 hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400'
            }`}
            id="toggle-anomalies-btn"
          >
            <div className={`w-2 h-2 rounded-full ${showAnomalies && !useELA ? 'bg-rose-500' : 'bg-gray-400'}`}></div>
            <span>Anomaly Areas</span>
          </button>

          {/* Lighting vectors toggle */}
          <button
            onClick={() => { setShowLighting(!showLighting); setUseELA(false); }}
            disabled={isScanning}
            className={`flex items-center space-x-2 px-3 py-2 rounded-xl text-left border text-xs font-medium transition ${
              showLighting && !useELA
                ? 'bg-teal-50 dark:bg-teal-950/20 border-teal-200 dark:border-teal-950/30 text-teal-700 dark:text-teal-400'
                : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-850 hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400'
            }`}
            id="toggle-lighting-btn"
          >
            <div className={`w-2 h-2 rounded-full ${showLighting && !useELA ? 'bg-teal-400' : 'bg-gray-400'}`}></div>
            <span>Lighting Angles</span>
          </button>

          {/* ELA filter toggle */}
          <button
            onClick={() => setUseELA(!useELA)}
            disabled={isScanning}
            className={`flex items-center space-x-2 px-3 py-2 rounded-xl text-left border text-xs font-medium transition ${
              useELA
                ? 'bg-purple-50 dark:bg-purple-950/20 border-purple-200 dark:border-purple-950/30 text-purple-700 dark:text-purple-400'
                : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-850 hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400'
            }`}
            id="toggle-ela-btn"
          >
            <div className={`w-2 h-2 rounded-full ${useELA ? 'bg-purple-500' : 'bg-gray-400'}`}></div>
            <span>Error Level (ELA)</span>
          </button>
        </div>
        <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-2 italic">
          Tip: Hover over markers and red bounding boxes on the media to read deep detailed forensic insights.
        </p>
      </div>
    </div>
  );
}
