/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Target, Search, Share2, CheckCircle2, RotateCw } from 'lucide-react';

interface LoggerPaneProps {
  isScanning: boolean;
  scanProgress: number;
}

export default function LoggerPane({ isScanning, scanProgress }: LoggerPaneProps) {
  // Step 1 ranges from 0 to 35%
  // Step 2 ranges from 35 to 70%
  // Step 3 ranges from 70 to 100%
  const getStepStatus = (step: 1 | 2 | 3) => {
    if (!isScanning && scanProgress === 0) return 'idle';
    if (scanProgress === 100) return 'completed';

    if (step === 1) {
      if (scanProgress < 35) return 'running';
      return 'completed';
    }
    if (step === 2) {
      if (scanProgress < 35) return 'pending';
      if (scanProgress < 75) return 'running';
      return 'completed';
    }
    if (step === 3) {
      if (scanProgress < 75) return 'pending';
      if (scanProgress < 100) return 'running';
      return 'completed';
    }
    return 'idle';
  };

  const steps = [
    {
      id: 1,
      title: 'Step 1: Biometric & Core Artifact Analysis',
      desc: 'Checking pixel compression noise, facial landmark uniformity, and skin tissue light reflectance.',
      icon: Target,
      subTasks: [
        'Mapping landmarks (3D wireframe mesh)',
        'Checking lighting angle continuity',
        'Detecting ear/eye structural symmetries'
      ]
    },
    {
      id: 2,
      title: 'Step 2: Digital Integrity & Artifact Sifting',
      desc: 'Detecting edge-blur anomalies, color-channel discrepancies, and temporal sync patterns.',
      icon: Search,
      subTasks: [
        'Evaluating high-frequency pixel seams',
        'Measuring phoneme mouth alignment',
        'Running Error Level (ELA) matrix computation'
      ]
    },
    {
      id: 3,
      title: 'Step 3: Public Registry & Circulation Search',
      desc: 'Cross-checking digital fingerprint against online indexes of flagged synthetic assets.',
      icon: Share2,
      subTasks: [
        'Generating digital media payload cryptographic hash',
        'Querying global historical deepfake database',
        'Analyzing propagation threat index'
      ]
    }
  ];

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          Investigation Lifecycle
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Progress of the multi-step digital forensics assessment.
        </p>
      </div>

      <div className="space-y-4">
        {steps.map((step) => {
          const status = getStepStatus(step.id as 1 | 2 | 3);
          const IconComponent = step.icon;

          return (
            <div
              key={step.id}
              className={`p-4 rounded-xl border text-left transition duration-300 ${
                status === 'running'
                  ? 'bg-sky-50/50 dark:bg-sky-950/10 border-sky-450 dark:border-sky-900/50'
                  : status === 'completed'
                  ? 'bg-emerald-50/20 dark:bg-emerald-950/5 border-emerald-200/55 dark:border-emerald-950/40'
                  : 'bg-gray-50/50 dark:bg-gray-950/40 border-gray-200 dark:border-gray-850 opacity-60'
              }`}
              id={`investigation-step-${step.id}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${
                    status === 'running'
                      ? 'bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400'
                      : status === 'completed'
                      ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                  }`}>
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-gray-900 dark:text-white">
                      {step.title}
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">
                      {step.desc}
                    </p>
                  </div>
                </div>

                <div>
                  {status === 'running' && (
                    <span className="flex items-center space-x-1 text-xs text-sky-600 dark:text-sky-400 font-mono font-bold animate-pulse">
                      <RotateCw className="w-3 h-3 animate-spin" />
                      <span>SCANNING</span>
                    </span>
                  )}
                  {status === 'completed' && (
                    <span className="flex items-center space-x-1 text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>COMPLETED</span>
                    </span>
                  )}
                  {status === 'pending' && (
                    <span className="text-[10px] text-gray-450 dark:text-gray-500 font-mono">
                      PENDING
                    </span>
                  )}
                  {status === 'idle' && (
                    <span className="text-[10px] text-gray-400 dark:text-gray-600 font-mono">
                      READY
                    </span>
                  )}
                </div>
              </div>

              {/* Subtask elements */}
              {status === 'running' && (
                <div className="mt-3 pl-11 space-y-1.5 border-l-2 border-sky-200 dark:border-sky-900 ml-4">
                  {step.subTasks.map((task, idx) => (
                    <div key={idx} className="flex items-center space-x-2 text-[10px] font-mono text-gray-600 dark:text-gray-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-ping"></span>
                      <span>{task}...</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
