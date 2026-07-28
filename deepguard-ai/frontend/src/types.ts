export interface AnalysisOverlay {
  id: string;
  type: 'landmark' | 'anomaly' | 'light_vector';
  x: number;
  y: number;
  w?: number;
  h?: number;
  label: string;
  description?: string;
}

export interface DiagnosticImages {
  ela?: string;
  fft?: string;
  dct?: string;
  wavelet_hh?: string;
  edges_canny?: string;
  edges_sobel?: string;
  edges_laplacian?: string;
}

export interface AnomalyRegion {
  x: number;
  y: number;
  w?: number;
  h?: number;
  label?: string;
  source?: string;
  intensity?: number;
}

export interface FrameAnalysisEntry {
  frame_index: number;
  verdict: string;
  confidence: number;
  raw_prob: number;
  summary: string;
}

export interface EvidenceTableEntry {
  round: number;
  capability: string;
  verdict: string;
  confidence: number;
  analysis_summary: string;
}

export interface InvestigationTrace {
  rounds_completed: number;
  providers_tried: string[];
  evidence_table: EvidenceTableEntry[];
  reasoning_log: string[];
  converged: boolean;
}

export interface BackendAnalysisResponse {
  verdict: string;
  confidence: number;
  confidence_percent: number;
  analysis_summary: string;
  forensic_observations: string[];
  visual_observations: string[];
  supporting_evidence: string[];
  conflicting_evidence: string[];
  limitations: string;
  recommendations: string[];
  explanation: string;
  key_indicators: string[];
  frame_analysis?: FrameAnalysisEntry[];
  raw_prob?: number;
  ela: { summary: string; diff_bbox?: unknown; mean_difference?: number };
  exif: { summary: string; exif: Record<string, unknown>; editing_software: string[]; ai_generation_tools: string[] };
  hash: { sha256: string; phash: string };
  noise: { noise_variance?: number; evidence: string };
  compression: { estimated_quality?: number; evidence: string };
  fft: { high_freq_ratio?: number; evidence: string };
  temporal: { frame_count: number; motion_score?: number; evidence: string };
  diagnostic_images: DiagnosticImages;
  anomaly_regions: AnomalyRegion[];
  pipeline: {
    routing: Record<string, unknown>;
    model_used: string;
    pipeline_time_seconds: number;
    fallback_triggered: boolean;
    degraded: boolean;
  };
  agent_logs: unknown[];
  request_id: string;
  report_text?: string;
  report_markdown?: string;
  investigation_trace?: InvestigationTrace;
}

export interface SampleMedia {
  id: string;
  title: string;
  type: 'image' | 'video';
  mimeType?: string;
  class: 'Real' | 'Fake' | 'Inconclusive';
  confidence: number;
  risk: 'Low' | 'Medium' | 'High';
  findings: string[];
  explanation: string;
  checkCirculating: string;
  url: string;
  category: string;
  overlays: AnalysisOverlay[];
  diagnosticImages?: DiagnosticImages;
  rawResponse?: BackendAnalysisResponse;
}

export interface ForensicLog {
  id: string;
  timestamp: string;
  message: string;
  status: 'info' | 'success' | 'warning' | 'error';
  delay: number;
}
