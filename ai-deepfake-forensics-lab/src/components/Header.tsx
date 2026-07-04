/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Shield, Home, Eye, ExternalLink, Mail, Circle } from 'lucide-react';

interface HeaderProps {
  activeTab: 'home' | 'samples' | 'test' | 'contact';
  setActiveTab: (tab: 'home' | 'samples' | 'test' | 'contact') => void;
}

export default function Header({ activeTab, setActiveTab }: HeaderProps) {
  const navItems = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'samples', label: 'Testing Samples', icon: Eye },
    { id: 'test', label: 'Test Your Media', icon: ExternalLink },
    { id: 'contact', label: 'Contact Us', icon: Mail }
  ] as const;

  return (
    <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-md sticky top-0 z-50 transition-all duration-300">
      <div className="max-w-[1200px] mx-auto px-5 py-3.5 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Brand/Logo Section */}
        <div 
          onClick={() => setActiveTab('home')}
          className="flex items-center space-x-3 cursor-pointer group"
        >
          <div className="p-2 bg-cyan-950/40 text-cyan-400 rounded-xl border border-cyan-900/40 group-hover:border-cyan-500/50 transition-all duration-300 shadow-[0_0_10px_rgba(34,211,238,0.1)]">
            <Shield className="w-5.5 h-5.5 animate-pulse" id="header-shield-icon" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black text-white tracking-tight">
                AI Forensics Lab
              </h1>
              <span className="flex items-center gap-1 text-[9px] font-mono bg-emerald-950/80 text-emerald-400 border border-emerald-900 px-1.5 py-0.5 rounded-full">
                <Circle className="w-1.5 h-1.5 fill-emerald-400 animate-ping" />
                SECURE NODE
              </span>
            </div>
            <p className="text-[10px] text-gray-500 font-mono tracking-wide">
              DEEP REGISTRY AUTHENTICATOR
            </p>
          </div>
        </div>

        {/* Dynamic Navigation Tabs */}
        <nav className="flex items-center bg-gray-900/60 p-1 rounded-xl border border-gray-805/80">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  isActive
                    ? 'bg-cyan-950/60 text-cyan-400 border border-cyan-900/50 shadow-[0_0_12px_rgba(34,211,238,0.1)]'
                    : 'text-gray-400 hover:text-white border border-transparent'
                }`}
                id={`nav-link-${item.id}`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
