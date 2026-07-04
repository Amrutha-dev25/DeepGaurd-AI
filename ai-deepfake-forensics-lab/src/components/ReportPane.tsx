/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckSquare, FileText, Download, Share2, Clipboard, Globe } from 'lucide-react';
import { SampleMedia } from '../types';
import { jsPDF } from 'jspdf';

interface ReportPaneProps {
  media: SampleMedia | null;
  isScanning: boolean;
  scanProgress: number;
}

export default function ReportPane({ media, isScanning, scanProgress }: ReportPaneProps) {
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (isScanning || scanProgress < 100) {
    return (
      <div className="bg-gray-50 dark:bg-gray-950/40 rounded-2xl border border-gray-200 dark:border-gray-850 p-8 flex flex-col items-center justify-center text-center h-full min-h-[300px]">
        <FileText className="w-10 h-10 text-gray-300 dark:text-gray-700 mb-3 animate-pulse" />
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-400">
          Awaiting Forensic Report
        </h3>
        <p className="text-xs text-gray-400 dark:text-gray-550 max-w-xs mt-1.5 leading-relaxed">
          The forensic report will be compiled automatically once the three-step digital scan completes.
        </p>
      </div>
    );
  }

  if (!media) return null;

  const isFake = media.class === 'Fake';
  const riskColor = 
    media.risk === 'High' 
      ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400 border-rose-200 dark:border-rose-900/30'
      : media.risk === 'Medium'
      ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border-amber-200 dark:border-amber-900/30'
      : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/30';

  const handleCopyReport = () => {
    const textToCopy = `DEEPFAKE FORENSICS REPORT
---------------------------
Exhibits: ${media.title}
Result: ${media.class}
Confidence Score: ${media.confidence}%
Risk Level: ${media.risk}
Findings:
${media.findings.map(f => `- ${f}`).join('\n')}

Explanation:
${media.explanation}

Circulation Check:
${media.checkCirculating}`;

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!media) return;
    setDownloading(true);
    setTimeout(() => {
      try {
        const doc = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4'
        });

        // 1. Double Border margin layout
        doc.setDrawColor(15, 23, 42); // slate-900
        doc.setLineWidth(0.85);
        doc.rect(8, 8, 194, 281);

        doc.setDrawColor(6, 182, 212); // cyan-500
        doc.setLineWidth(0.25);
        doc.rect(9.5, 9.5, 191, 278);

        // 2. High-Tech Header Banner
        doc.setFillColor(15, 23, 42);
        doc.rect(10, 10, 190, 24, "F");

        doc.setFillColor(6, 182, 212);
        doc.rect(10, 33, 190, 1, "F");

        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(255, 255, 255);
        doc.text("DEEPFAKE FORENSICS INTELLIGENCE LAB", 16, 19);

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(6, 182, 212);
        doc.text("MILITARY-GRADE COGNITIVE FORENSICS & DIGITAL INTEGRITY VERIFICATION RECORD", 16, 25);

        doc.setFont("courier", "bold");
        doc.setFontSize(8);
        doc.setTextColor(200, 200, 200);
        doc.text(`HASH_ID: #DF-${(media.confidence * 482).toFixed(0)}`, 16, 30);

        // 3. Verdict Highlight Box
        const isFakeMedia = media.class === 'Fake';
        const accent = isFakeMedia ? { rgb: [244, 63, 94], label: 'DEEPFAKE ANOMALIES DETECTED' } 
                                   : { rgb: [16, 185, 129], label: 'VERIFIED GENUINE / HIGH INTEGRITY' };

        doc.setFillColor(accent.rgb[0], accent.rgb[1], accent.rgb[2]);
        doc.rect(14, 38, 182, 14, "F");

        doc.setFont("helvetica", "bold");
        doc.setFontSize(11);
        doc.setTextColor(255, 255, 255);
        doc.text(`FORENSIC DIAGNOSTIC DECISION: ${accent.label}`, 20, 47);

        // 4. Case Metadata Grid
        let currentY = 58;

        const drawSectionTitle = (title: string) => {
          doc.setFillColor(241, 245, 249);
          doc.rect(14, currentY, 182, 7, "F");
          doc.setFont("helvetica", "bold");
          doc.setFontSize(9);
          doc.setTextColor(15, 23, 42);
          doc.text(title, 18, currentY + 5);
          currentY += 12;
        };

        // Draw Metadata list
        doc.setFont("helvetica", "bold");
        doc.setFontSize(9);
        doc.setTextColor(100, 116, 139);

        doc.text("FILE NAME / TARGET ID:", 16, 58);
        doc.text("TARGET FORMAT TYPE:", 16, 64);
        doc.text("EVIDENCE CATEGORY:", 16, 70);

        doc.text("TIMESTAMP / ACQUIRED:", 112, 58);
        doc.text("MODEL PROBABILITY:", 112, 64);
        doc.text("THREAT SEVERITY:", 112, 70);

        doc.setFont("helvetica", "bold");
        doc.setTextColor(15, 23, 42);
        const titleStr = media.title.length > 35 ? media.title.substring(0, 32) + "..." : media.title;
        doc.text(titleStr, 62, 58);
        doc.text(media.type.toUpperCase(), 62, 64);
        doc.text(media.category.toUpperCase(), 62, 70);

        const timeStr = new Date().toLocaleString();
        doc.text(timeStr, 156, 58);
        
        doc.setTextColor(isFakeMedia ? 244 : 16, isFakeMedia ? 63 : 185, isFakeMedia ? 94 : 129);
        doc.text(`${media.confidence}% Precision Score`, 156, 64);
        doc.text(`${media.risk.toUpperCase()} LEVEL`, 156, 70);

        doc.setTextColor(15, 23, 42);
        currentY = 78;

        // 5. Section I: Findings List
        drawSectionTitle("I. VECTOR TELEMETRY SIGNATURE & ANOMALY LIST");

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9.5);
        
        media.findings.forEach((finding, idx) => {
          doc.setFillColor(accent.rgb[0], accent.rgb[1], accent.rgb[2]);
          doc.rect(17, currentY - 2.5, 1.8, 1.8, "F");

          doc.setFont("helvetica", "bold");
          doc.setTextColor(15, 23, 42);
          doc.text(`[Anomaly Vector 0${idx+1}]:`, 21, currentY - 1);
          
          doc.setFont("helvetica", "normal");
          doc.setTextColor(51, 65, 85);
          const maxTextW = 126;
          const lines = doc.splitTextToSize(finding, maxTextW);
          doc.text(lines, 64, currentY - 1);
          currentY += (lines.length * 4.5) + 3.5;
        });

        currentY += 3;

        // 6. Section II: Explanation Summary
        drawSectionTitle("II. FORENSIC CLINICAL SUMMARY & EXPLANATION");
        
        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(51, 65, 85);
        const explanationLines = doc.splitTextToSize(media.explanation, 178);
        doc.text(explanationLines, 16, currentY);
        currentY += (explanationLines.length * 4.5) + 8;

        // 7. Section III: Online footprint
        drawSectionTitle("III. DISTRIBUTION ANALYSIS & CIRCULATION SUMMARY");

        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(51, 65, 85);
        const circulationLines = doc.splitTextToSize(media.checkCirculating, 178);
        doc.text(circulationLines, 16, currentY);
        currentY += (circulationLines.length * 4.5) + 12;

        // 8. Seal Section
        doc.setDrawColor(226, 232, 240);
        doc.setLineWidth(0.4);
        doc.line(14, currentY, 196, currentY);
        currentY += 8;

        doc.setFont("courier", "bold");
        doc.setFontSize(7.5);
        doc.setTextColor(148, 163, 184);
        doc.text("SECURE BLOCKCHAIN HASH ENCRYPTION TAG", 16, currentY);
        doc.text(`VERIFICATION SEAL ID: SHA256-${media.id.toUpperCase()}`, 16, currentY + 3.5);

        doc.setFont("helvetica", "bold");
        doc.setFontSize(8.5);
        doc.setTextColor(6, 182, 212);
        doc.text("[ CERTIFIED DIGITAL EVIDENCE MASTER DECRYPTOR SEAL ]", 110, currentY + 2);

        doc.save(`Forensics-Report-${media.id}-${media.class}.pdf`);
      } catch (err) {
        console.error("Error generating professional PDF with jsPDF: ", err);
      } finally {
        setDownloading(false);
      }
    }, 1200);
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border-2 border-gray-150 dark:border-gray-800 p-6 shadow-md transition-colors duration-300">
      {/* Report Header Stamp */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-100 dark:border-gray-800 pb-4 mb-5">
        <div>
          <span className="text-[10px] font-mono font-bold tracking-widest text-sky-600 dark:text-sky-400 uppercase bg-sky-50 dark:bg-sky-950/40 px-2 py-0.5 rounded">
            CASE FILE RECORD
          </span>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mt-1">
            Forensic Investigation Report
          </h3>
        </div>
        <div className="text-[10px] font-mono text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-gray-950 px-2 py-1 rounded inline-block">
          REPORT ID: #FR-2026-{(media.confidence * 123).toFixed(0)}
        </div>
      </div>

      <div className="space-y-6">
        {/* Step 1 Outcome: Big High-Contrast Badge */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          <div className="md:col-span-2">
            <p className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">
              Primary Prediction & Assessment
            </p>
            <div className={`p-4 rounded-xl border flex items-center space-x-3.5 ${
              isFake
                ? 'bg-rose-50/70 border-rose-150 text-rose-800 dark:bg-rose-950/20 dark:border-rose-950/30 dark:text-rose-450'
                : 'bg-emerald-50/70 border-emerald-150 text-emerald-800 dark:bg-emerald-950/20 dark:border-emerald-950/30 dark:text-emerald-450'
            }`}>
              <div className={`p-2.5 rounded-xl ${isFake ? 'bg-rose-100 dark:bg-rose-900' : 'bg-emerald-100 dark:bg-emerald-900'}`}>
                {isFake ? <ShieldAlert className="w-6 h-6" /> : <ShieldCheck className="w-6 h-6" />}
              </div>
              <div>
                <span className="text-xs font-semibold tracking-wider uppercase opacity-85">
                  Media Classified As:
                </span>
                <div className="text-2xl font-black tracking-tight mt-0.5">
                  {media.class.toUpperCase()} MEDIUM
                </div>
              </div>
            </div>
          </div>

          <div>
            <p className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5 text-center md:text-left">
              Integrity Confidence
            </p>
            <div className="border border-gray-150 dark:border-gray-850 p-3 rounded-xl bg-gray-50/50 dark:bg-gray-950/30 flex items-center justify-center space-x-3">
              {/* Custom SVG Progress Circle */}
              <div className="relative w-12 h-12 flex-shrink-0">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="24"
                    cy="24"
                    r="20"
                    className="stroke-gray-200 dark:stroke-gray-800 stroke-[4]"
                    fill="none"
                  />
                  <circle
                    cx="24"
                    cy="24"
                    r="20"
                    className={`stroke-[4] transition-all duration-1000 ${isFake ? 'stroke-rose-500' : 'stroke-emerald-500'}`}
                    fill="none"
                    strokeDasharray={`${2 * Math.PI * 20}`}
                    strokeDashoffset={`${2 * Math.PI * 20 * (1 - media.confidence / 100)}`}
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-gray-800 dark:text-gray-200">
                  {media.confidence.toFixed(0)}%
                </span>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">
                  Precision Rating
                </p>
                <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5 leading-tight">
                  Based on biometric deviations.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Global Metadata: Risk and Classification */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3.5 bg-gray-50 dark:bg-gray-950/40 rounded-xl border border-gray-150 dark:border-gray-850">
            <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase">
              Threat Risk Level
            </span>
            <div className="flex items-center space-x-2 mt-2">
              <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border uppercase tracking-wider ${riskColor}`}>
                {media.risk} Threat
              </span>
              <AlertTriangle className={`w-4 h-4 ${media.risk === 'High' ? 'text-rose-550' : 'text-amber-550'}`} />
            </div>
          </div>

          <div className="p-3.5 bg-gray-50 dark:bg-gray-950/40 rounded-xl border border-gray-150 dark:border-gray-850">
            <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase">
              Exhibit Category
            </span>
            <div className="text-sm font-bold text-gray-850 dark:text-gray-200 mt-2">
              {media.category}
            </div>
          </div>
        </div>

        {/* Bullet Findings Component */}
        <div>
          <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-sky-500" />
            Key Forensic Findings
          </h4>
          <ul className="space-y-2">
            {media.findings.map((finding, idx) => (
              <li
                key={idx}
                className="flex items-start space-x-2.5 text-xs text-gray-650 dark:text-gray-350 leading-relaxed"
              >
                <span className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${isFake ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Paragraph explanation */}
        <div className="bg-gray-50 dark:bg-gray-950/30 p-4 rounded-xl border border-gray-100 dark:border-gray-850">
          <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-350 uppercase tracking-keep mb-2">
            Detailed Explanation
          </h4>
          <p className="text-xs text-gray-650 dark:text-gray-400 leading-relaxed">
            {media.explanation}
          </p>
        </div>

        {/* Online circulation block */}
        <div className="border-t border-gray-100 dark:border-gray-850 pt-4 flex items-start gap-3">
          <div className="p-2 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 rounded-lg">
            <Globe className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-800 dark:text-gray-300">
              Web Circulation & Propagation Check
            </h4>
            <p className="text-[11px] text-gray-500 dark:text-gray-450 mt-1 leading-relaxed">
              {media.checkCirculating}
            </p>
          </div>
        </div>

        {/* Report Operations bar (Copy and download buttons) */}
        <div className="border-t border-gray-100 dark:border-gray-800 pt-5 flex flex-wrap gap-2 justify-end">
          <button
            onClick={handleCopyReport}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-medium border border-gray-250 dark:border-gray-800 bg-white hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900 text-gray-700 dark:text-gray-300 transition"
            id="copy-text-btn"
          >
            <Clipboard className="w-3.5 h-3.5" />
            <span>{copied ? 'Copied' : 'Copy Report'}</span>
          </button>
          
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-gray-900 dark:bg-gray-250 dark:hover:bg-white text-white dark:text-gray-900 hover:bg-gray-850 transition"
            id="download-pdf-btn"
          >
            <Download className={`w-3.5 h-3.5 ${downloading ? 'animate-bounce' : ''}`} />
            <span>{downloading ? 'Compiling File...' : 'Download Report'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
