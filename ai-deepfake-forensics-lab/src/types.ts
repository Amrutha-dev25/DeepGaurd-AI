/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface AnalysisOverlay {
  id: string;
  type: 'landmark' | 'anomaly' | 'light_vector';
  x: number; // percentage from left
  y: number; // percentage from top
  w?: number; // size width for anomaly
  h?: number; // size height for anomaly
  label: string;
  description?: string;
}

export interface SampleMedia {
  id: string;
  title: string;
  type: 'image' | 'video';
  class: 'Real' | 'Fake';
  confidence: number; // 0 to 100
  risk: 'Low' | 'Medium' | 'High';
  findings: string[];
  explanation: string;
  checkCirculating: string;
  url: string;
  category: string;
  overlays: AnalysisOverlay[];
}

export interface ForensicLog {
  id: string;
  timestamp: string;
  message: string;
  status: 'info' | 'success' | 'warning' | 'error';
  delay: number; // simulated progression delay in milliseconds
}
