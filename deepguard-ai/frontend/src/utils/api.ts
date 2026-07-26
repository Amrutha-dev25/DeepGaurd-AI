import { SampleMedia, AnalysisOverlay, BackendAnalysisResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function analyzeMedia(file: File): Promise<SampleMedia> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Backend error: ${response.statusText}`);
  }

  const data: BackendAnalysisResponse = await response.json();

  const url = URL.createObjectURL(file);
  const mimeType = file.type;
  const type = mimeType.startsWith('video/') ? 'video' : 'image';

  let suspectClass: 'Real' | 'Fake' | 'Inconclusive';
  let risk: 'Low' | 'Medium' | 'High';
  let category: string;

  const v = data.verdict;
  if (v === 'inconclusive' || v === 'error') {
    suspectClass = 'Inconclusive';
    risk = 'Medium';
    category = v === 'error' ? 'Analysis Error' : 'Inconclusive Result';
  } else if (v === 'fake') {
    suspectClass = 'Fake';
    risk = 'High';
    category = 'Suspected Manipulation';
  } else {
    suspectClass = 'Real';
    risk = 'Low';
    category = 'Authentic Record';
  }

  const findings: string[] = [];

  if (Array.isArray(data.forensic_observations) && data.forensic_observations.length > 0) {
    data.forensic_observations.forEach((obs: string) => findings.push(obs));
  }
  if (Array.isArray(data.visual_observations) && data.visual_observations.length > 0) {
    data.visual_observations.forEach((obs: string) => findings.push(`[Visual] ${obs}`));
  }
  if (Array.isArray(data.supporting_evidence) && data.supporting_evidence.length > 0) {
    data.supporting_evidence.forEach((ev: string) => findings.push(`[Supporting] ${ev}`));
  }
  if (Array.isArray(data.conflicting_evidence) && data.conflicting_evidence.length > 0) {
    data.conflicting_evidence.forEach((ev: string) => findings.push(`[Conflict] ${ev}`));
  }
  if (data.limitations) {
    findings.push(`[Limitation] ${data.limitations}`);
  }

  if (findings.length === 0 && Array.isArray(data.key_indicators)) {
    data.key_indicators.forEach((k: string) => findings.push(k));
  }

  if (findings.length === 0) {
    if (data.ela?.summary) findings.push(`ELA: ${data.ela.summary}`);
    if (data.exif?.summary) findings.push(`EXIF: ${data.exif.summary}`);
    if (data.hash?.sha256) findings.push(`SHA-256: ${data.hash.sha256.slice(0, 32)}...`);
    if (data.noise?.evidence) findings.push(`Noise: ${data.noise.evidence}`);
    if (data.compression?.evidence) findings.push(`Compression: ${data.compression.evidence}`);
    if (data.fft?.evidence) findings.push(`FFT: ${data.fft.evidence}`);
  }

  const overlays: AnalysisOverlay[] = [];
  if (Array.isArray(data.anomaly_regions)) {
    data.anomaly_regions.forEach((region: any, idx: number) => {
      overlays.push({
        id: `anomaly-${idx}`,
        type: 'anomaly',
        x: region.x,
        y: region.y,
        w: region.w,
        h: region.h,
        label: region.label || 'Anomaly Region',
        description: region.source
          ? `Detected via ${region.source} (intensity: ${region.intensity || 'N/A'})`
          : 'Forensic anomaly region',
      });
    });
  }

  const hasConflicts = Array.isArray(data.conflicting_evidence) && data.conflicting_evidence.length > 0;
  const recommendations = hasConflicts
    ? `Conflicting evidence detected: ${data.conflicting_evidence.join('; ')}. ${(Array.isArray(data.recommendations) ? data.recommendations.join(' ') : 'Manual review recommended.')}`
    : (Array.isArray(data.recommendations)
      ? data.recommendations.join(' ')
      : 'No recommendations available.');

  return {
    id: `deepguard-${Date.now()}`,
    title: file.name,
    type,
    mimeType,
    class: suspectClass,
    confidence: data.confidence,
    risk,
    findings: findings.length > 0 ? findings : ['No forensic data available.'],
    explanation: data.analysis_summary || data.explanation || 'Forensic analysis completed.',
    checkCirculating: recommendations,
    url,
    category,
    overlays,
    diagnosticImages: data.diagnostic_images,
    rawResponse: data,
  };
}
