import {
  Terminal, Search, Code, TerminalSquare, GitBranch
} from 'lucide-react';
import type { AgentConfig } from '@/types/api.types';

// --- CONFIGURAZIONE AGENTI ---
export const AGENT_CONFIG: Record<string, AgentConfig> = {
  Architect: {
    color: "text-purple-400",
    border: "border-purple-500/30",
    bg: "bg-purple-500/10",
    icon: <Search size={12} />
  },
  Coder: {
    color: "text-blue-400",
    border: "border-blue-500/30",
    bg: "bg-blue-500/10",
    icon: <Code size={12} />
  },
  Compiler: {
    color: "text-orange-400",
    border: "border-orange-500/30",
    bg: "bg-orange-500/10",
    icon: <TerminalSquare size={12} />
  },
  Manager: {
    color: "text-pink-400",
    border: "border-pink-500/30",
    bg: "bg-pink-500/10",
    icon: <GitBranch size={12} />
  },
  System: {
    color: "text-slate-400",
    border: "border-slate-700",
    bg: "bg-slate-800",
    icon: <Terminal size={12} />
  }
};

export const getAgentConfig = (name?: string): AgentConfig => {
  if (name?.toLowerCase().includes("team")) return AGENT_CONFIG.Manager;
  const key = Object.keys(AGENT_CONFIG).find(k => name?.includes(k)) || "System";
  return AGENT_CONFIG[key];
};