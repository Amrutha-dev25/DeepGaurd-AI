/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Shield, ChevronUp, Github, Heart } from 'lucide-react';

interface FooterProps {
  activeTab: 'home' | 'samples' | 'test' | 'contact';
  setActiveTab: (tab: 'home' | 'samples' | 'test' | 'contact') => void;
}

export default function Footer({ activeTab, setActiveTab }: FooterProps) {
  const scrolltoTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer 
      id="app-main-footer"
      className="bg-black/80 border-t border-gray-900 py-12 px-5 md:py-16 relative z-20 backdrop-blur-md overflow-hidden font-sans"
    >
      {/* Decorative subtle background highlights */}
      <div className="absolute -bottom-12 -left-12 w-64 h-64 bg-cyan-900/5 rounded-full blur-[80px] pointer-events-none" />
      <div className="absolute -top-12 -right-12 w-64 h-64 bg-blue-900/5 rounded-full blur-[80px] pointer-events-none" />

      <div className="max-w-[1200px] mx-auto flex flex-col md:flex-row items-center justify-between gap-8 text-center md:text-left relative z-10">
        
        {/* Left Side: Brand and Tagline */}
        <div id="footer-branding" className="space-y-3.5 max-w-md">
          <div 
            onClick={() => { setActiveTab('home'); scrolltoTop(); }} 
            className="flex items-center justify-center md:justify-start space-x-2.5 cursor-pointer group"
          >
            <div className="p-1.5 bg-cyan-950/40 text-cyan-400 rounded-lg border border-cyan-900/40 group-hover:border-cyan-500/50 transition-all duration-300">
              <Shield className="w-4.5 h-4.5" />
            </div>
            <span className="text-sm font-black text-white tracking-widest uppercase">
              Deepfake Forensics Intelligence Lab
            </span>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed max-w-sm">
            AI-powered forensic analysis for digital media. Extract biological anomalies, pupillary reflection lighting vectors, and spatial noise anomalies offline.
          </p>
        </div>

        {/* Center/Right Side: Dynamic Navigation Links */}
        <div id="footer-navigation" className="flex flex-col sm:flex-row items-center gap-6 sm:gap-10">
          <div className="flex flex-wrap justify-center gap-5 text-xs text-gray-400 font-medium">
            <button
              onClick={() => { setActiveTab('home'); scrolltoTop(); }}
              className={`hover:text-cyan-400 transition-colors duration-200 ${activeTab === 'home' ? 'text-cyan-400 font-bold' : ''}`}
              id="footer-link-home"
            >
              Home
            </button>
            <button
              onClick={() => { setActiveTab('samples'); scrolltoTop(); }}
              className={`hover:text-cyan-400 transition-colors duration-200 ${activeTab === 'samples' ? 'text-cyan-400 font-bold' : ''}`}
              id="footer-link-samples"
            >
              Exhibits Archive
            </button>
            <button
              onClick={() => { setActiveTab('test'); scrolltoTop(); }}
              className={`hover:text-cyan-400 transition-colors duration-200 ${activeTab === 'test' ? 'text-cyan-400 font-bold' : ''}`}
              id="footer-link-test"
            >
              Sandbox Workbench
            </button>
            <button
              onClick={() => { setActiveTab('contact'); scrolltoTop(); }}
              className={`hover:text-cyan-400 transition-colors duration-200 ${activeTab === 'contact' ? 'text-cyan-400 font-bold' : ''}`}
              id="footer-link-contact"
            >
              Intake Portal
            </button>
          </div>

          {/* Scroll to Top Trigger */}
          <button
            onClick={scrolltoTop}
            className="p-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-cyan-900 text-gray-400 hover:text-cyan-400 rounded-xl transition-all duration-300"
            title="Scroll to Top"
            id="footer-scroll-to-top"
          >
            <ChevronUp className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Underline Sub-Footer Bar */}
      <div className="max-w-[1200px] mx-auto mt-10 pt-6 border-t border-gray-900/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-gray-500 font-mono">
        <div>
          <span>© {new Date().getFullYear()} Deepfake Forensics Intelligence Lab. Secure cryptographic workspace.</span>
        </div>
        <div className="flex items-center gap-1.5 grayscale opacity-60 hover:grayscale-0 hover:opacity-100 transition-all duration-200">
          <span>Protected status: active</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      </div>
    </footer>
  );
}
