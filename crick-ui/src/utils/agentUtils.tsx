import {
  Terminal, Search, Code, TerminalSquare, GitBranch
} from 'lucide-react';
import type { AgentConfig } from '@/types/api.types';

// --- CONFIGURAZIONE AGENTI ---
export const AGENT_CONFIG: Record<string, AgentConfig> = {
  Architect: {
    color: "text-purple-600 dark:text-purple-400",
    border: "border-purple-200 dark:border-purple-500/30",
    bg: "bg-purple-50 dark:bg-purple-500/10",
    icon: <Search size={12} />
  },
  Coder: {
    color: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-200 dark:border-emerald-500/30",
    bg: "bg-emerald-50 dark:bg-emerald-500/10",
    icon: <Code size={12} />
  },
  Compiler: {
    color: "text-orange-600 dark:text-orange-400",
    border: "border-orange-200 dark:border-orange-500/30",
    bg: "bg-orange-50 dark:bg-orange-500/10",
    icon: <TerminalSquare size={12} />
  },
  Manager: {
    color: "text-pink-600 dark:text-pink-400",
    border: "border-pink-200 dark:border-pink-500/30",
    bg: "bg-pink-50 dark:bg-pink-500/10",
    icon: <GitBranch size={12} />
  },
  System: {
    color: "text-gray-500 dark:text-slate-400",
    border: "border-gray-200 dark:border-slate-700",
    bg: "bg-gray-100 dark:bg-slate-800",
    icon: <Terminal size={12} />
  }
};

export const getAgentConfig = (name?: string): AgentConfig => {
  if (name?.toLowerCase().includes("team")) return AGENT_CONFIG.Manager;
  const key = Object.keys(AGENT_CONFIG).find(k => name?.includes(k)) || "System";
  return AGENT_CONFIG[key];
};