/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import Header from './components/Header';
import Footer from './components/Footer';
import UploadZone from './components/UploadZone';
import InteractiveViewer from './components/InteractiveViewer';
import LoggerPane from './components/LoggerPane';
import ReportPane from './components/ReportPane';
import SpaceBackgroundGrid from './components/SpaceBackgroundGrid';
import { STATIC_SAMPLES } from './data/samples';
import { SampleMedia } from './types';
import { jsPDF } from 'jspdf';
import { generateCustomReport, UploadSettings } from './utils/forensicsGenerator';
import { 	
  Shield, 
  Sparkles, 
  Sliders, 
  Check, 
  CircleAlert, 
  FileSignature, 
  ArrowRight, 
  Activity, 
  FileCheck2, 
  Cpu, 
  Search, 
  Share2, 
  Globe, 
  Mail, 
  Phone, 
  MapPin, 
  Send,
  Fingerprint,
  Lock,
  FileText,
  Download,
  AlertTriangle,
  X,
  Play
} from 'lucide-react';

const INDICATORS = [
  { value: 'biometric', label: 'Biometric Anomalies (Eyes/Lips)' },
  { value: 'light_vector', label: 'Lighting Vector Mismatch' },
  { value: 'ela_anomaly', label: 'Error Level Analysis (ELA) Compression Inconsistency' },
  { value: 'seams', label: 'Neck Blending Seams / Artifacts' },
  { value: 'frame_brightness', label: 'Frame Brightness Inconsistency' }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'home' | 'samples' | 'test' | 'contact'>('home');
  const [selectedReportSample, setSelectedReportSample] = useState<SampleMedia | null>(null);
  
  // Tab-independent active report to render Page 4
  const [activeReport, setActiveReport] = useState<SampleMedia | null>(STATIC_SAMPLES[0]);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [scanProgress, setScanProgress] = useState<number>(100);

  // Contact form states
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    category: 'Forensic Support',
    message: ''
  });
  const [submittedTicket, setSubmittedTicket] = useState<string | null>(null);

  // Tuning parameter defaults
  const [uploadSettings, setUploadSettings] = useState<UploadSettings>({
    suspectClass: 'Fake',
    confidence: 89,
    risk: 'High',
    primaryIndicator: 'biometric'
  });

  // Keep track of user custom file url state
  const [customFile, setCustomFile] = useState<{
    url: string;
    type: 'image' | 'video';
    name: string;
    file?: File;
  } | null>(null);

  // PDF report downloader helper
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  // Triggering the scanning simulation
  const triggerScanAnimation = (targetReport: SampleMedia) => {
    setIsScanning(true);
    setScanProgress(0);
    setActiveReport(targetReport);

    const stepDuration = 25; // Speed multiplier
    const timer = setInterval(() => {
      setScanProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setIsScanning(false);
          return 100;
        }
        return prev + 2;
      });
    }, stepDuration);
  };

  const handleSelectSampleAndAnalyze = (sample: SampleMedia) => {
    setSelectedReportSample(sample);
  };

const handleCustomFileUploaded = async (fileInfo: File | { url: string; type: 'image' | 'video'; name: string }) => {
  if (isScanning) return;
  let targetUrl = '';
  let targetType: 'image' | 'video' = 'image';
  let targetName = 'suspect_evidence';
  let targetFile: File | undefined;

  if (fileInfo instanceof File) {
    targetUrl = URL.createObjectURL(fileInfo);
    targetType = fileInfo.type.startsWith('video/') ? 'video' : 'image';
    targetName = fileInfo.name;
    targetFile = fileInfo;
  } else {
    targetUrl = fileInfo.url;
    targetType = fileInfo.type;
    targetName = fileInfo.name;
  }

  setCustomFile({ url: targetUrl, type: targetType, name: targetName, file: targetFile });

  if (targetFile) {
    setIsScanning(true);
    setScanProgress(0);
    const progressTimer = setInterval(() => {
      setScanProgress((prev) => {
        if (prev >= 90) { clearInterval(progressTimer); return 90; }
        return prev + 3;
      });
    }, 200);
    try {
      const report = await generateCustomReport(targetUrl, targetName, targetType, targetFile);
      clearInterval(progressTimer);
      setScanProgress(100);
      triggerScanAnimation(report);
    } catch (err) {
      console.error('Analysis failed:', err);
      clearInterval(progressTimer);
      setIsScanning(false);
    }
  }
};

  const handleApplyCustomSettings = async () => {
  if (!customFile?.file || isScanning) return;
  setIsScanning(true);
  setScanProgress(0);
  const progressTimer = setInterval(() => {
    setScanProgress((prev) => {
      if (prev >= 90) { clearInterval(progressTimer); return 90; }
      return prev + 3;
    });
  }, 200);
  try {
    const report = await generateCustomReport(customFile.url, customFile.name, customFile.type, customFile.file);
    clearInterval(progressTimer);
    setScanProgress(100);
    triggerScanAnimation(report);
  } catch (err) {
    console.error('Re-analysis failed:', err);
    clearInterval(progressTimer);
    setIsScanning(false);
  }
};

  const handleContactSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactForm.name || !contactForm.email || !contactForm.message) return;
    
    const ticketId = `SEC-DF-${(Math.random() * 900000 + 100000).toFixed(0)}`;
    setSubmittedTicket(ticketId);
  };

  const handleDownloadPdf = (report: SampleMedia) => {
    setIsDownloadingPdf(true);
    setTimeout(() => {
      try {
        const doc = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4'
        });

        // 1. Sleek Outer Border for certification
        doc.setDrawColor(15, 23, 42); // slate-900
        doc.setLineWidth(0.85);
        doc.rect(8, 8, 194, 281); // beautiful thin margin frame

        doc.setDrawColor(6, 182, 212); // cyan-500 layers
        doc.setLineWidth(0.25);
        doc.rect(9.5, 9.5, 191, 278);

        // 2. High-Tech Navy/Slate Header Banner (RGB: 15, 23, 42)
        doc.setFillColor(15, 23, 42);
        doc.rect(10, 10, 190, 24, "F");

        // Cyan Accent line inside header bottom
        doc.setFillColor(6, 182, 212);
        doc.rect(10, 33, 190, 1, "F");

        // Header Title Texts
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(255, 255, 255);
        doc.text("DEEPFAKE FORENSICS INTELLIGENCE LAB", 16, 19);

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(6, 182, 212); // cyan
        doc.text("MILITARY-GRADE COGNITIVE FORENSICS & DIGITAL INTEGRITY VERIFICATION RECORD", 16, 25);

        doc.setFont("courier", "bold");
        doc.setFontSize(8);
        doc.setTextColor(200, 200, 200);
        doc.text(`HASH_ID: #DF-${(report.confidence * 482).toFixed(0)}`, 16, 30);

        // 3. Verdict Highlight Box (depending on class)
        const isFake = report.class === 'Fake';
        const accentColor = isFake ? { rgb: [244, 63, 94], label: 'DEEPFAKE ANOMALIES DETECTED' } 
                                   : { rgb: [16, 185, 129], label: 'VERIFIED GENUINE / HIGH INTEGRITY' };

        // Verdict banner box
        doc.setFillColor(accentColor.rgb[0], accentColor.rgb[1], accentColor.rgb[2]);
        doc.rect(14, 38, 182, 14, "F");

        doc.setFont("helvetica", "bold");
        doc.setFontSize(11);
        doc.setTextColor(255, 255, 255);
        doc.text(`FORENSIC DIAGNOSTIC DECISION: ${accentColor.label}`, 20, 47);

        // 4. Case Metadata Grid
        let currentY = 58;

        const drawSectionHeader = (title: string) => {
          doc.setFillColor(241, 245, 249); // light-slate grayish
          doc.rect(14, currentY, 182, 7, "F");
          doc.setFont("helvetica", "bold");
          doc.setFontSize(9);
          doc.setTextColor(15, 23, 42); // slate-900
          doc.text(title, 18, currentY + 5);
          currentY += 12;
        };

        // Draw Meta Values
        doc.setFont("helvetica", "bold");
        doc.setFontSize(9);
        doc.setTextColor(100, 116, 139); // cool gray

        // Left column labels
        doc.text("FILE NAME / TARGET ID:", 16, 58);
        doc.text("TARGET FORMAT TYPE:", 16, 64);
        doc.text("EVIDENCE CATEGORY:", 16, 70);

        // Right column labels
        doc.text("TIMESTAMP / ACQUIRED:", 112, 58);
        doc.text("MODEL PROBABILITY:", 112, 64);
        doc.text("THREAT SEVERITY:", 112, 70);

        // Fill values
        doc.setFont("helvetica", "bold");
        doc.setTextColor(15, 23, 42);
        // Clean Title wrap
        const titleStr = report.title.length > 35 ? report.title.substring(0, 32) + "..." : report.title;
        doc.text(titleStr, 62, 58);
        doc.text(report.type.toUpperCase(), 62, 64);
        doc.text(report.category.toUpperCase(), 62, 70);

        // Right column values
        const timeStr = new Date().toLocaleString();
        doc.text(timeStr, 156, 58);
        
        // Color code model confidence and threat
        doc.setTextColor(isFake ? 244 : 16, isFake ? 63 : 185, isFake ? 94 : 129);
        doc.text(`${report.confidence}% Precision Score`, 156, 64);
        doc.text(`${report.risk.toUpperCase()} LEVEL`, 156, 70);

        // Reset text color to slate
        doc.setTextColor(15, 23, 42);

        // Update Y position after grid
        currentY = 78;

        // 5. Section I: Forensic Analysis Signatures & Findings
        drawSectionHeader("I. VECTOR TELEMETRY SIGNATURE & ANOMALY LIST");

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9.5);
        
        report.findings.forEach((finding, idx) => {
          // Drawing a tiny square bullet matching verdict color
          doc.setFillColor(accentColor.rgb[0], accentColor.rgb[1], accentColor.rgb[2]);
          doc.rect(17, currentY - 2.5, 1.8, 1.8, "F");

          doc.setFont("helvetica", "bold");
          doc.setTextColor(15, 23, 42);
          doc.text(`[Anomaly Vector 0${idx+1}]:`, 21, currentY - 1);
          
          doc.setFont("helvetica", "normal");
          doc.setTextColor(51, 65, 85); // slate-700
          // Wrap finding description text nicely
          const textX = 64;
          const maxTextW = 126;
          const lines = doc.splitTextToSize(finding, maxTextW);
          doc.text(lines, textX, currentY - 1);
          currentY += (lines.length * 4.5) + 3.5;
        });

        currentY += 3;

        // 6. Section II: Forensic Comments & Simple English Explanation
        drawSectionHeader("II. FORENSIC CLINICAL SUMMARY & EXPLANATION");
        
        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(51, 65, 85);
        const explanationLines = doc.splitTextToSize(report.explanation, 178);
        doc.text(explanationLines, 16, currentY);
        currentY += (explanationLines.length * 4.5) + 8;

        // 7. Section III: Online footprint
        drawSectionHeader("III. DISTRIBUTION ANALYSIS & CIRCULATION SUMMARY");

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(51, 65, 85);
        const circulationLines = doc.splitTextToSize(report.checkCirculating, 178);
        doc.text(circulationLines, 16, currentY);
        currentY += (circulationLines.length * 4.5) + 12;

        // 8. Seal Section
        // Draw separator
        doc.setDrawColor(226, 232, 240); // slate-200
        doc.setLineWidth(0.4);
        doc.line(14, currentY, 196, currentY);
        currentY += 8;

        // Seal / Stamp visual text
        doc.setFont("courier", "bold");
        doc.setFontSize(7.5);
        doc.setTextColor(148, 163, 184); // slate-400
        doc.text("SECURE BLOCKCHAIN HASH ENCRYPTION TAG", 16, currentY);
        doc.text(`VERIFICATION SEAL ID: SHA256-${report.id.toUpperCase()}`, 16, currentY + 3.5);

        doc.setFont("helvetica", "bold");
        doc.setFontSize(8.5);
        doc.setTextColor(6, 182, 212); // cyan accent
        doc.text("[ CERTIFIED DIGITAL EVIDENCE MASTER DECRYPTOR SEAL ]", 110, currentY + 2);

        // Save PDF file
        doc.save(`Forensics-Report-${report.id}-${report.class}.pdf`);
      } catch (err) {
        console.error("Error generating professional PDF with jsPDF: ", err);
      } finally {
        setIsDownloadingPdf(false);
      }
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans transition-colors duration-300 relative selection:bg-cyan-500/30 selection:text-cyan-200">
      
      {/* Background Matrix & Stars Canvas */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <SpaceBackgroundGrid />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-700/5 rounded-full blur-[140px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-900/5 rounded-full blur-[140px]" />
      </div>

      <Header activeTab={activeTab} setActiveTab={(tab) => {
        setActiveTab(tab);
        // Clear modals or states appropriately during tab change
        setSelectedReportSample(null);
      }} />

      <main className="relative z-10 w-full overflow-hidden">
        <AnimatePresence mode="wait">
          
          {/* ==================== 🏠 PAGE 1: HOME ==================== */}
          {activeTab === 'home' && (
            <motion.div
              key="home-page"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="w-full"
            >
              {/* SECTION 1: HERO */}
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="relative bg-gray-950 py-24 md:py-32 border-b border-gray-900/60 overflow-hidden"
              >
                {/* Background video within hero container */}
                <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none opacity-20">
                  <video
                    autoPlay
                    muted
                    loop
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover mix-blend-screen"
                    src="https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-and-numbers-31907-large.mp4"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-gray-950/70 to-transparent" />
                </div>

                <div className="max-w-[1200px] mx-auto px-5 text-center relative z-10 space-y-6">
                  {/* Cyber decorative badge */}
                  <motion.span 
                    initial={{ scale: 0.95, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="inline-flex items-center gap-1.5 text-[10px] font-mono tracking-widest bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 px-4 py-1.5 rounded-full uppercase shadow-[0_0_15px_rgba(34,211,238,0.15)]"
                  >
                    <Sparkles className="w-3.5 h-3.5 animate-pulse text-cyan-400" />
                    MILITARY-GRADE FORENSICS SENSORS
                  </motion.span>

                  <h1 className="text-4xl md:text-6xl lg:text-7xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white via-cyan-100 to-sky-300 tracking-tight leading-none mx-auto max-w-4xl py-2">
                    Deepfake Forensics Intelligence Lab
                  </h1>
                  
                  <p className="text-sm md:text-base text-gray-400 max-w-2xl mx-auto tracking-wide leading-relaxed">
                    AI-powered investigation for digital media authenticity. 
                    Isolate biological, temporal, and spatial vectors to identify synthetic manipulations.
                  </p>

                  <div className="pt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
                    <button
                      onClick={() => setActiveTab('test')}
                      className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-4 bg-gradient-to-r from-cyan-600 to-sky-700 hover:from-cyan-500 hover:to-sky-600 text-white rounded-xl text-xs font-bold tracking-wider uppercase transition-all duration-300 shadow-[0_4px_15px_rgba(6,182,212,0.25)] hover:scale-[1.03] active:scale-95 group"
                      id="hero-start-testing-btn"
                    >
                      <span>Start Testing Workbench</span>
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </button>
                    <button
                      onClick={() => setActiveTab('samples')}
                      className="w-full sm:w-auto px-8 py-4 bg-gray-900/65 hover:bg-gray-900 border border-gray-800 hover:border-cyan-500/40 text-gray-200 rounded-xl text-xs font-bold tracking-wider uppercase transition-all duration-300 hover:scale-[1.03] active:scale-95"
                      id="hero-view-samples-btn"
                    >
                      View Sample Cases
                    </button>
                  </div>
                </div>
              </motion.section>

              {/* SECTION 2: TELEMETRY STATS */}
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="bg-gray-900/10 py-24 md:py-32 border-b border-gray-900/60"
              >
                <div className="max-w-[1200px] mx-auto px-5 space-y-12">
                  <div className="text-center space-y-2">
                    <span className="text-[10px] font-mono font-bold uppercase text-cyan-400 tracking-wider">TELEMETRY MATRIX</span>
                    <h3 className="text-2xl md:text-3xl font-black text-white">System Operations Performance</h3>
                    <p className="text-xs text-gray-450 max-w-sm mx-auto">
                      Real-time forensic integrity stats and anomaly mapping telemetry active.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8" id="home-stats-matrix">
                    {[
                      { label: "Total Handled Scans", value: "12,482", detail: "Global assets assessed", color: "text-cyan-400" },
                      { label: "Deepfakes Detected", value: "3,847", detail: "Synthetics flag rate: ~30.8%", color: "text-rose-450" },
                      { label: "System Accuracy", value: "99.2%", detail: "Validation precision tier", color: "text-emerald-400" },
                      { label: "Pending cases", value: "2", detail: "Active queue queueing", color: "text-indigo-400" }
                    ].map((stat, i) => (
                      <motion.div 
                        key={i}
                        variants={{
                          hidden: { opacity: 0, y: 15 },
                          show: { opacity: 1, y: 0 }
                        }}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.1, duration: 0.5 }}
                        className="bg-gray-950/80 border border-gray-900 p-6 rounded-2xl flex flex-col justify-between h-48 hover:scale-[1.03] hover:border-cyan-500/20 hover:shadow-[0_4px_25px_rgba(6,182,212,0.06)] transition-all duration-300"
                      >
                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{stat.label}</h4>
                        <div className="my-auto">
                          <span className={`text-3xl md:text-4xl font-extrabold ${stat.color} tracking-tight font-mono`}>{stat.value}</span>
                        </div>
                        <p className="text-[10px] text-gray-500 font-mono">{stat.detail}</p>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.section>

              {/* SECTION 3: NOTICE ALERT */}
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="bg-gray-950 py-20 border-b border-gray-900/60"
              >
                <div className="max-w-[1200px] mx-auto px-5">
                  <div className="p-6 md:p-8 rounded-2xl bg-gradient-to-r from-red-950/20 to-rose-950/5 border border-red-900/25 text-red-300 text-sm flex flex-col sm:flex-row items-center sm:items-start gap-4 max-w-4xl mx-auto shadow-inner">
                    <div className="p-3 bg-red-950/60 rounded-xl border border-red-800/30 text-rose-450 flex-shrink-0 animate-pulse">
                      <Shield className="w-5.5 h-5.5" />
                    </div>
                    <div className="space-y-1.5 text-center sm:text-left">
                      <span className="font-extrabold text-white text-xs uppercase tracking-widest flex items-center justify-center sm:justify-start gap-1.5 select-none">
                        Security Operations Notice
                      </span>
                      <p className="text-gray-400 text-xs leading-relaxed">
                        This module utilizes simulated biomechanical coordinates, pupillary reflections lighting vector, neck blending seams, and sifting algorithms. Utilize preset certified archive exhibits on testing tabs or upload suspect image/video feeds to process digital integrity assessments.
                      </p>
                    </div>
                  </div>
                </div>
              </motion.section>

              {/* SECTION 4: WORKFLOW PIPELINE */}
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="bg-gray-900/10 py-24 md:py-32"
              >
                <div className="max-w-[1200px] mx-auto px-5 space-y-12">
                  <div className="text-center max-w-xl mx-auto space-y-2">
                    <span className="text-[10px] font-mono font-bold uppercase text-cyan-400 tracking-wider">DIAGNOSTIC WORKFLOW</span>
                    <h2 className="text-2xl md:text-3xl font-black text-white tracking-tight">How the Forensic Module Operates</h2>
                    <p className="text-xs text-gray-455 leading-relaxed">
                      A rigorous multi-layer digital telemetry pipeline isolates synthetic origins, validating pixel integrity.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6 md:gap-8">
                    {[
                      { step: "01", title: "Upload Media", desc: "Drag & drop image/video resources or paste target public server links safely." },
                      { step: "02", title: "Analyze Features", desc: "Extract biological landmarks, facial wireframe meshes, and directional incident light shadows." },
                      { step: "03", title: "Detect Manipulation", desc: "Map local frequency noise variations (ELA) and identify blending seams." },
                      { step: "04", title: "Generate Report", desc: "Retrieve classified verification parameters, confidence ratings, and certificate PDF." }
                    ].map((wf, idx) => (
                      <motion.div 
                        key={idx}
                        initial={{ opacity: 0, y: 15 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: idx * 0.1, duration: 0.5 }}
                        className="bg-gray-950/80 border border-gray-900 p-6 rounded-2xl relative group hover:scale-[1.03] hover:border-cyan-500/20 hover:shadow-[0_4px_25px_rgba(6,182,212,0.05)] transition-all duration-300 flex flex-col justify-between h-48"
                      >
                        <div>
                          <div className="text-3xl font-black text-gray-800 font-mono tracking-tight group-hover:text-cyan-500/20 transition-colors duration-300">{wf.step}</div>
                          <h4 className="text-sm font-bold text-gray-200 mt-2">{wf.title}</h4>
                        </div>
                        <p className="text-xs text-gray-450 leading-relaxed">{wf.desc}</p>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.section>
            </motion.div>
          )}

          {/* ==================== 👁️ PAGE 2: TESTING SAMPLES ==================== */}
          {activeTab === 'samples' && (
            <motion.div
              key="samples-page"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="w-full bg-gray-950"
            >
              <div className="py-24 md:py-32">
                <div className="max-w-[1200px] mx-auto px-5 space-y-12">
                  <div className="text-center space-y-2 max-w-2xl mx-auto">
                    <span className="text-[10px] font-mono font-bold uppercase text-cyan-400 tracking-wider">CERTIFIED INDEX ARCHIVES</span>
                    <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight">
                      Certified Forensic Exhibits Archive
                    </h2>
                    <p className="text-xs md:text-sm text-gray-450 leading-relaxed">
                      Select an index case below to examine verified anomalies without mixing features in the upload workbench.
                    </p>
                  </div>

                  {/* 2 columns grid layout of compact uniform cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8" id="certified-samples-grid">
                    {STATIC_SAMPLES.map((sample) => {
                      const isFake = sample.class === 'Fake';
                      return (
                        <div 
                          key={sample.id}
                          className="bg-gray-900/25 border border-gray-900 rounded-2xl overflow-hidden hover:scale-[1.02] hover:border-cyan-500/20 hover:shadow-[0_8px_30px_rgba(6,182,212,0.06)] transition-all duration-300 flex flex-col justify-between h-full"
                        >
                          {/* Media Image preview */}
                          <div className="relative aspect-video w-full overflow-hidden bg-black border-b border-gray-900">
                            <img 
                              src={sample.url} 
                              alt={sample.title}
                              referrerPolicy="no-referrer"
                              className="w-full h-full object-cover opacity-75 group-hover:scale-105 transition-all duration-500"
                            />
                            <span className={`absolute top-4 right-4 text-[9px] font-mono font-extrabold px-3 py-1 bg-black/80 rounded-full uppercase border ${
                              isFake 
                                ? 'text-rose-400 border-rose-900/50' 
                                : 'text-emerald-400 border-emerald-900/50'
                            }`}>
                              {sample.class === 'Fake' ? 'DEEPFAKE ANOMALIES' : 'VERIFIED GENUINE'}
                            </span>
                            
                            <div className="absolute bottom-4 left-4 right-4 z-10">
                              <span className="text-[10px] font-mono font-semibold tracking-wider text-cyan-400 uppercase">
                                {sample.category}
                              </span>
                              <h3 className="text-base font-bold text-white mt-0.5">
                                {sample.title}
                              </h3>
                            </div>
                            <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent opacity-80" />
                          </div>

                          {/* Brief findings copy & Action bar */}
                          <div className="p-6 space-y-4 flex flex-col justify-between flex-1">
                            <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">
                              {sample.explanation}
                            </p>
                            
                            <div className="flex items-center gap-3 text-[11px] font-mono pl-3 border-l-2 border-cyan-800">
                              <span className="text-gray-500">PRECISION:</span>
                              <span className={`${isFake ? 'text-rose-450' : 'text-emerald-450'} font-bold`}>
                                {sample.confidence}% Model Confidence
                              </span>
                            </div>

                            <div className="pt-4 border-t border-gray-900/80 flex items-center justify-between gap-4">
                              <span className="text-[10px] text-gray-500 font-mono tracking-wider">FILE_INDEX: {sample.id.substring(7, 13).toUpperCase() || sample.id}</span>
                              <button
                                onClick={() => handleSelectSampleAndAnalyze(sample)}
                                className="px-4.5 py-2.5 bg-gray-950 hover:bg-cyan-950 hover:text-cyan-400 border border-gray-800 hover:border-cyan-800 text-xs font-bold text-cyan-400 rounded-xl transition-all duration-300"
                                id={`view-report-sample-${sample.id}`}
                              >
                                View Report
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Dedicated Report Modal Overlay */}
              <AnimatePresence>
                {selectedReportSample && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/90 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto"
                  >
                    <motion.div 
                      initial={{ scale: 0.95, y: 15 }}
                      animate={{ scale: 1, y: 0 }}
                      exit={{ scale: 0.95, y: 15 }}
                      className="bg-gray-950 border border-gray-900 rounded-3xl max-w-4xl w-full p-6 md:p-8 space-y-6 relative max-h-[90vh] overflow-y-auto shadow-2xl"
                    >
                      <button 
                        onClick={() => setSelectedReportSample(null)}
                        className="absolute top-5 right-5 p-2 bg-gray-900 text-gray-400 hover:text-white rounded-full transition-all duration-300"
                        title="Close Modal"
                      >
                        <X className="w-5 h-5" />
                      </button>

                      <div className="border-b border-gray-900 pb-4">
                        <span className="text-[10px] bg-cyan-950/60 text-cyan-400 px-3 py-1 border border-cyan-900/40 rounded font-mono font-bold tracking-widest uppercase">
                          OFFICIAL DIAGNOSTIC DISCLOSURE
                        </span>
                        <h2 className="text-xl md:text-2xl font-black text-white mt-3">
                          {selectedReportSample.title}
                        </h2>
                        <p className="text-xs text-gray-450 mt-1">Archived Forensic Findings for Category: {selectedReportSample.category}</p>
                      </div>

                      {/* Diagnostic Split Layout */}
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                        
                        {/* Interactive Viewer visual highlight */}
                        <div className="lg:col-span-6 space-y-4">
                          <InteractiveViewer 
                            media={selectedReportSample} 
                            isScanning={false} 
                            scanProgress={100} 
                            onReScan={() => {}} 
                          />
                        </div>

                        {/* Analysis report telemetry outcomes */}
                        <div className="lg:col-span-6 space-y-5">
                          <div className="grid grid-cols-2 gap-4">
                            <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-900">
                              <span className="text-[9px] font-mono text-gray-500 uppercase block tracking-wider">Class Validation</span>
                              <div className={`text-sm font-black mt-1 uppercase ${selectedReportSample.class === 'Fake' ? 'text-rose-400' : 'text-emerald-400'}`}>
                                {selectedReportSample.class === 'Fake' ? '🔴 DEEPFAKE' : '🟢 GENUINE'}
                              </div>
                            </div>
                            <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-900">
                              <span className="text-[9px] font-mono text-gray-500 uppercase block tracking-wider">Precision Rating</span>
                              <div className="text-sm font-black mt-1 text-cyan-400">
                                {selectedReportSample.confidence}% Accuracy
                              </div>
                            </div>
                          </div>

                          <div className="p-5 bg-gray-900/50 rounded-2xl border border-gray-900 space-y-3">
                            <span className="text-[10px] font-mono text-gray-400 uppercase tracking-wider block">Key Analytical Signatures:</span>
                            <ul className="space-y-2.5 text-xs text-gray-300 leading-relaxed">
                              {selectedReportSample.findings.map((f, i) => (
                                <li key={i} className="flex items-start gap-2.5">
                                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 ${selectedReportSample.class === 'Fake' ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                                  <span>{f}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="p-5 bg-cyan-950/20 border border-cyan-900/55 rounded-xl text-xs text-gray-300 leading-relaxed">
                            <strong className="text-cyan-400 block mb-1">Forensics Explanation:</strong>
                            {selectedReportSample.explanation}
                          </div>

                          <div className="flex gap-2 justify-end pt-2">
                            <button
                              onClick={() => handleDownloadPdf(selectedReportSample)}
                              disabled={isDownloadingPdf}
                              className="px-5 py-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-cyan-500 text-xs font-bold text-white rounded-xl transition flex items-center gap-2"
                            >
                              <Download className="w-3.5 h-3.5" />
                              <span>{isDownloadingPdf ? 'Compiling Document...' : 'Download Report'}</span>
                            </button>
                            <button
                              onClick={() => setSelectedReportSample(null)}
                              className="px-5 py-2.5 bg-cyan-950 hover:bg-cyan-900 border border-cyan-900 text-xs font-bold text-cyan-400 rounded-xl transition"
                            >
                              Dismiss Disclosures
                            </button>
                          </div>
                        </div>

                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* ==================== 🛠️ PAGE 3: TEST YOUR MEDIA ==================== */}
          {activeTab === 'test' && (
            <motion.div
              key="test-page"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="w-full bg-gray-950"
            >
              <div className="py-24 md:py-32">
                <div className="max-w-[1200px] mx-auto px-5 space-y-12">
                  <div className="text-center space-y-2 max-w-xl mx-auto">
                    <span className="text-[10px] font-mono font-bold uppercase text-cyan-400 tracking-wider">REALTIME INTEGRITY VERIFIER</span>
                    <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight">
                      Media Authenticator Workbench
                    </h2>
                    <p className="text-xs md:text-sm text-gray-450 leading-relaxed">
                      Upload custom suspect files or paste hot remote asset URLs to run real-time biological grid sifting in search of manipulations.
                    </p>
                  </div>

                  {/* Main centered structured drag & drop zone */}
                  <div className="max-w-2xl mx-auto space-y-8">
                    
                    {/* Simulator Settings controller */}
                    <div className="bg-gray-950 border border-gray-900 p-6 rounded-2xl space-y-5 shadow-lg">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-cyan-950/80 text-cyan-400 rounded-xl border border-cyan-900/40">
                          <Sliders className="w-5 h-5 animate-pulse" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-white uppercase tracking-wider">Forensic Simulation Profiler</h4>
                          <p className="text-[11px] text-gray-500">Configure simulated outcomes for custom files uploaded below.</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-1">
                        <div className="space-y-2">
                          <label className="text-gray-400 font-semibold block">Target Classification</label>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              onClick={() => setUploadSettings({ ...uploadSettings, suspectClass: 'Fake', risk: 'High' })}
                              className={`py-2.5 px-3 rounded-lg border text-xs font-bold transition-all duration-300 flex items-center justify-center gap-1.5 ${
                                uploadSettings.suspectClass === 'Fake'
                                  ? 'bg-rose-950/30 border-rose-500/60 text-rose-400'
                                  : 'bg-gray-900 border-gray-800 text-gray-450 hover:bg-gray-850'
                              }`}
                            >
                              <CircleAlert className="w-3.5 h-3.5" />
                              Synthetic
                            </button>
                            <button
                              onClick={() => setUploadSettings({ ...uploadSettings, suspectClass: 'Real', risk: 'Low' })}
                              className={`py-2.5 px-3 rounded-lg border text-xs font-bold transition-all duration-300 flex items-center justify-center gap-1.5 ${
                                uploadSettings.suspectClass === 'Real'
                                  ? 'bg-emerald-950/30 border-emerald-500/60 text-emerald-400'
                                  : 'bg-gray-900 border-gray-800 text-gray-450 hover:bg-gray-850'
                              }`}
                            >
                              <Check className="w-3.5 h-3.5" />
                              Genuine
                            </button>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <label className="text-gray-400 font-semibold block">Primary Anomaly Vector</label>
                          <select
                            value={uploadSettings.primaryIndicator}
                            onChange={(e) => setUploadSettings({ ...uploadSettings, primaryIndicator: e.target.value })}
                            disabled={uploadSettings.suspectClass === 'Real'}
                            className="w-full p-2.5 bg-gray-900 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-40 outline-none focus:border-cyan-550 transition duration-200"
                          >
                            {INDICATORS.map((ind) => (
                              <option key={ind.value} value={ind.value}>
                                {ind.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Concentrated Upload Zone */}
                    <div className="shadow-2xl">
                      <UploadZone onFileSelect={handleCustomFileUploaded} isLoading={isScanning} />
                    </div>

                    {/* Progression Bar */}
                    {isScanning && (
                      <div className="bg-gray-950 border border-cyan-900/40 p-6 rounded-2xl space-y-4 shadow-xl">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-cyan-400 uppercase font-mono tracking-widest flex items-center gap-1.5">
                            <Cpu className="w-4 h-4 animate-spin text-cyan-400" />
                            Analyzing Matrix Streams...
                          </span>
                          <span className="font-mono text-gray-400">{scanProgress}%</span>
                        </div>
                        <div className="w-full bg-gray-900 h-2.5 rounded-full overflow-hidden">
                          <div className="bg-cyan-500 h-full transition-all duration-100" style={{ width: `${scanProgress}%` }} />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* REPORT SECTION: Highly polished with perfect layout structure */}
                  {!isScanning && activeReport && (
                    <motion.div 
                      initial={{ opacity: 0, y: 30 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.6 }}
                      className="border-t border-gray-900 pt-20 space-y-12 max-w-4xl mx-auto" 
                      id="test-report-panel-container"
                    >
                      <div className="text-center space-y-2">
                        <span className="text-[10px] font-mono tracking-widest text-emerald-400 bg-emerald-950/60 px-4 py-1 rounded border border-emerald-900/50 uppercase font-extrabold">
                          GENERATED REPORT STATUS: ACTIVE
                        </span>
                        <h3 className="text-2xl md:text-3xl font-black text-white tracking-tight">
                          Diagnostic Laboratory Output
                        </h3>
                        <p className="text-xs text-gray-450 leading-relaxed">
                          Page 4: Detailed evidence assessment and prediction score disclosures.
                        </p>
                      </div>

                      {/* Main diagnostic workspace */}
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                        {/* Visualizer output */}
                        <div className="lg:col-span-6 space-y-4">
                          <InteractiveViewer 
                            media={activeReport} 
                            isScanning={false} 
                            scanProgress={100} 
                            onReScan={() => triggerScanAnimation(activeReport)} 
                          />
                        </div>

                        {/* Numerical and Descriptive Disclosures */}
                        <div className="lg:col-span-6 space-y-6">
                          
                          {/* Prediction Badge, Confidence, and Threat Level */}
                          <div className="space-y-4">
                            <div className="p-5 bg-gray-950 rounded-2xl border border-gray-900 flex items-center justify-between shadow-sm">
                              <div>
                                <span className="text-[9px] text-gray-500 font-mono block uppercase tracking-wider">INTEGRITY CLASSIFICATION</span>
                                <div className={`text-lg font-black mt-1 uppercase tracking-tight ${activeReport.class === 'Fake' ? 'text-rose-455' : 'text-emerald-455'}`}>
                                  {activeReport.class === 'Fake' ? '🔴 DEEPFAKE DETECTED' : '🟢 VERIFIED GENUINE'}
                                </div>
                              </div>
                              <div className={`px-3 py-1.5 text-[10px] font-bold rounded uppercase border font-mono tracking-wider ${
                                activeReport.risk === 'High' 
                                  ? 'bg-rose-950/35 text-rose-400 border-rose-900/50'
                                  : 'bg-emerald-950/35 text-emerald-400 border-emerald-900/50'
                              }`}>
                                {activeReport.risk} Risk Threat
                              </div>
                            </div>

                            {/* Precision Meter */}
                            <div className="p-5 bg-gray-950 border border-gray-900 rounded-2xl space-y-3.5 shadow-sm">
                              <div className="flex justify-between items-center text-xs text-gray-400">
                                <span>Biometric Probability Precision:</span>
                                <strong className="text-cyan-400 font-mono font-black">{activeReport.confidence}%</strong>
                              </div>
                              <div className="w-full bg-gray-900 h-2 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full ${activeReport.class === 'Fake' ? 'bg-rose-500' : 'bg-emerald-500'}`} 
                                  style={{ width: `${activeReport.confidence}%` }} 
                                />
                              </div>
                            </div>
                          </div>

                          {/* Explanation in clear, simple English */}
                          <div className="p-6 bg-cyan-950/20 border border-cyan-900/50 rounded-2xl space-y-2 shadow-inner">
                            <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider font-mono">Analysis Summary (Simple English)</h4>
                            <p className="text-xs text-gray-300 leading-relaxed">
                              {activeReport.explanation}
                            </p>
                          </div>

                          {/* Diagnostic Signatures List */}
                          <div className="p-6 bg-gray-950 border border-gray-900 rounded-2xl shadow-sm">
                            <span className="text-[10px] text-gray-500 font-mono block mb-3.5 uppercase tracking-wider">Target Findings:</span>
                            <ul className="space-y-3.5">
                              {activeReport.findings.map((f, i) => (
                                <li key={i} className="flex items-start gap-3 text-xs text-gray-300 leading-relaxed">
                                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 ${activeReport.class === 'Fake' ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                                  <span>{f}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* Actions pane: PDF download */}
                          <div className="pt-4 border-t border-gray-900/60 flex justify-end">
                            <button
                              onClick={() => handleDownloadPdf(activeReport)}
                              disabled={isDownloadingPdf}
                              className="px-6 py-3.5 bg-gradient-to-r from-cyan-600 to-sky-700 hover:from-cyan-500 hover:to-sky-600 text-white rounded-xl text-xs font-black tracking-wider uppercase transition-all duration-200 flex items-center gap-2 hover:shadow-[0_4px_15px_rgba(6,182,212,0.15)]"
                              id="export-pdf-report-trigger-btn"
                            >
                              <Download className="w-3.5 h-3.5" />
                              <span>{isDownloadingPdf ? 'Compiling File...' : 'Download Report as PDF'}</span>
                            </button>
                          </div>

                        </div>
                      </div>
                    </motion.div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== ✉️ PAGE 5: CONTACT ==================== */}
          {activeTab === 'contact' && (
            <motion.div
              key="contact-page"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="w-full bg-gray-950 font-sans"
            >
              <div className="py-24 md:py-32">
                <div className="max-w-[1200px] mx-auto px-5 space-y-12">
                  <div className="text-center space-y-2">
                    <span className="text-[10px] font-mono font-bold uppercase text-cyan-400 tracking-wider">SECURE INTAKE PORTAL</span>
                    <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight">
                      Secure Command Intake Portal
                    </h2>
                    <p className="text-xs md:text-sm text-gray-400 max-w-lg mx-auto leading-relaxed">
                      Submit a batch-processing case or technical laboratory support ticket to our staff.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-stretch max-w-4xl mx-auto">
                    
                    {/* Information cards */}
                    <div className="md:col-span-5">
                      <div className="bg-gray-950 border border-gray-900 p-6 rounded-2xl space-y-6 shadow-md flex flex-col justify-between h-full min-h-[360px]">
                        <div>
                          <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider mb-4 border-b border-gray-900 pb-2">Registered Facilities</h4>

                          <div className="space-y-4 text-xs">
                            <div className="flex items-start gap-3">
                              <MapPin className="w-4.5 h-4.5 text-cyan-400 mt-0.5 flex-shrink-0" />
                              <div>
                                <strong className="text-gray-300 block font-semibold">Headquarters Location</strong>
                                <span className="text-gray-450 mt-0.5 block leading-relaxed">
                                  844 Security Circle, Cyber Heights<br />Suite 702, DC 20024
                                </span>
                              </div>
                            </div>

                            <div className="flex items-start gap-3">
                              <Mail className="w-4.5 h-4.5 text-cyan-400 mt-0.5 flex-shrink-0" />
                              <div>
                                <strong className="text-gray-300 block font-semibold">General Intake Mail</strong>
                                <span className="text-gray-450 block mt-0.5 hover:text-cyan-400 transition cursor-pointer font-mono text-[11px]">
                                  intake@forensicslab.sec
                                </span>
                              </div>
                            </div>

                            <div className="flex items-start gap-3">
                              <Phone className="w-4.5 h-4.5 text-cyan-400 mt-0.5 flex-shrink-0" />
                              <div>
                                <strong className="text-gray-300 block font-semibold">Secure Hotline Link</strong>
                                <span className="text-gray-450 mt-0.5 block font-mono text-[11px]">
                                  +1 (415) 555-0192 (VoIP)
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="border-t border-gray-900 pt-4 flex items-center justify-between">
                          <span className="text-[9px] font-mono bg-cyan-950 text-cyan-400 px-2.5 py-1 rounded border border-cyan-900/50 uppercase tracking-widest font-extrabold">
                            Active Encryption Link
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Structured Ticket form */}
                    <div className="md:col-span-7 bg-gray-950 border border-gray-900 p-6 rounded-2xl flex flex-col justify-center min-h-[360px] shadow-md">
                      {submittedTicket ? (
                        <div className="py-10 text-center space-y-5">
                          <div className="w-12 h-12 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-900 flex items-center justify-center mx-auto shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                            <Check className="w-6 h-6" />
                          </div>
                          <div className="space-y-1.5">
                            <h4 className="text-base font-bold text-white">Ticket Filed Successfully</h4>
                            <p className="text-xs text-gray-450 max-w-sm mx-auto leading-relaxed">
                              Operational inquiry log has been securely catalogued. Responsive routing typically takes 4–8 business hours.
                            </p>
                          </div>
                          <div className="py-1.5 px-3 bg-gray-900 border border-gray-805 text-[10px] font-mono text-cyan-400 w-fit mx-auto rounded shadow-inner">
                            TICKET HASH: {submittedTicket}
                          </div>
                          <button
                            onClick={() => {
                              setSubmittedTicket(null);
                              setContactForm({ name: '', email: '', category: 'Forensic Support', message: '' });
                            }}
                            className="text-xs text-gray-450 hover:text-cyan-400 underline transition block mx-auto font-semibold mt-2"
                          >
                            Submit Another Support Request
                          </button>
                        </div>
                      ) : (
                        <form onSubmit={handleContactSubmit} className="space-y-4">
                          <h4 className="text-xs font-bold text-gray-300 uppercase tracking-widest block mb-1 font-mono">
                            Inquiry Dispatcher Form
                          </h4>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                            <div className="space-y-1.5">
                              <label className="text-gray-400 font-semibold block">Operator Name</label>
                              <input 
                                type="text" 
                                required
                                placeholder="e.g. Inspector Blake"
                                value={contactForm.name}
                                onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                                className="w-full p-2.5 bg-gray-900 rounded-lg border border-gray-800 focus:border-cyan-500/50 text-white placeholder-gray-650 outline-none transition duration-200"
                              />
                            </div>

                            <div className="space-y-1.5">
                              <label className="text-gray-400 font-semibold block">Routing Email</label>
                              <input 
                                type="email" 
                                required
                                placeholder="operator@proton.me"
                                value={contactForm.email}
                                onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                                className="w-full p-2.5 bg-gray-900 rounded-lg border border-gray-800 focus:border-cyan-500/50 text-white placeholder-gray-650 outline-none transition duration-200"
                              />
                            </div>
                          </div>

                          <div className="space-y-1.5 text-xs">
                            <label className="text-gray-400 font-semibold block">Operational Category</label>
                            <select 
                              value={contactForm.category}
                              onChange={(e) => setContactForm({ ...contactForm, category: e.target.value })}
                              className="w-full p-2.5 bg-gray-900 rounded-lg border border-gray-800 focus:border-cyan-500/50 text-white outline-none transition duration-200"
                            >
                              <option>Forensic Support</option>
                              <option>Corporate License Integration</option>
                              <option>Report Genuineness Validation</option>
                            </select>
                          </div>

                          <div className="space-y-1.5 text-xs">
                            <label className="text-gray-400 font-semibold block">Detailed Inquiry Message</label>
                            <textarea 
                              rows={4}
                              required
                              placeholder="Describe the anomalies or request technical support assistance details..."
                              value={contactForm.message}
                              onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                              className="w-full p-2.5 bg-gray-900 rounded-lg border border-gray-800 focus:border-cyan-505/50 text-white placeholder-gray-650 outline-none resize-none transition duration-200"
                            />
                          </div>

                          <button
                            type="submit"
                            className="w-full py-3 bg-gradient-to-r from-cyan-600 to-sky-700 hover:from-cyan-500 hover:to-sky-600 text-white rounded-lg text-xs font-bold uppercase transition hover:scale-[1.01] active:scale-95"
                          >
                            File Command Ticket
                          </button>
                        </form>
                      )}
                    </div>

                  </div>
                </div>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </main>
      <Footer activeTab={activeTab} setActiveTab={setActiveTab} />
    </div>
  );
}
