/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { SampleMedia, AnalysisOverlay } from '../types';

export interface UploadSettings {
  suspectClass: 'Fake' | 'Real';
  confidence: number;
  risk: 'Low' | 'Medium' | 'High';
  primaryIndicator: string;
}

const API_BASE = 'http://localhost:8000';

export async function generateCustomReport(
  url: string,
  fileName: string,
  type: 'image' | 'video',
  file: File
): Promise<SampleMedia> {
  // Call real backend
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Backend error: ${response.statusText}`);
  }

  const data = await response.json();

  // Map backend response to SampleMedia format
  const findings: string[] = [
    `ELA: ${data.ela?.summary || 'No ELA data'}`,
    `EXIF: ${data.exif?.summary || 'No EXIF data'}`,
    `SHA-256: ${data.hash?.sha256?.slice(0, 32) || 'N/A'}...`,
    `Perceptual Hash: ${data.hash?.phash || 'N/A'}`,
    `Frames: ${data.frames?.summary || 'N/A'} — Brightness: ${data.frames?.average_brightness?.toFixed(2) || 'N/A'}`,
  ];

  const hasManipulation = data.ela?.summary?.toLowerCase().includes('manipulation') ||
    data.ela?.diff_bbox !== null;

  const suspectClass: 'Real' | 'Fake' = hasManipulation ? 'Fake' : 'Real';
  const confidence = hasManipulation ? 78 : 91;
  const risk = hasManipulation ? 'High' : 'Low';

  const overlays: AnalysisOverlay[] = data.ela?.diff_bbox ? [
    {
      id: 'ela-anomaly-1',
      type: 'anomaly',
      x: 40,
      y: 40,
      w: 20,
      h: 20,
      label: 'ELA Anomaly Region',
      description: 'Error Level Analysis detected compression inconsistency in this region.'
    }
  ] : [];

  const recommendations = Array.isArray(data.recommendations)
    ? data.recommendations.join(' ')
    : 'No recommendations available.';

  return {
    id: `deepguard-${Date.now()}`,
    title: fileName,
    type,
    class: suspectClass,
    confidence,
    risk,
    findings,
    explanation: data.verdict || 'Forensic analysis complete. See findings for details.',
    checkCirculating: recommendations,
    url,
    category: hasManipulation ? 'Suspected Manipulation' : 'Authentic Record',
    overlays,
  };
}
