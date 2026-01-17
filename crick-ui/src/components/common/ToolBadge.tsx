import React, { useMemo } from 'react';
import { Loader2, Check, Wrench } from 'lucide-react';
import { getAgentConfig } from '@/utils/agentUtils';

export interface ToolBadgeProps {
  tool: string;
  args?: any;
  status: 'running' | 'completed';
  agent: string;
}

const ToolBadgeComponent: React.FC<ToolBadgeProps> = ({ tool, args, status, agent }) => {
  const config = useMemo(() => getAgentConfig(agent), [agent]);

  const argsStr = useMemo(() => {
    if (!args) return null;
    if (typeof args === 'string') return args;
    try {
      return Object.entries(args)
        .map(([key, value]) => {
          let v = String(value);
          if (v.length > 50) v = v.slice(0, 50) + '...';
          return `${key}: "${v}"`;
        })
        .join(', ');
    } catch {
      return "args...";
    }
  }, [args]);

  return (
    <div className={`flex flex-col my-2 pl-2 border-l-2 border-gray-200 dark:border-[#3e3e42] animate-in fade-in`}>
      <div className="flex items-center gap-2 text-[10px] font-mono">
        {status === 'running' ? (
          <Loader2 size={10} className={`animate-spin ${config.color}`} />
        ) : (
          <Check size={10} className="text-emerald-500" />
        )}
        <span className={`font-bold uppercase opacity-70 ${config.color}`}>{agent}</span>
        <span className="text-gray-500 dark:text-slate-500">
          executes <strong className="text-gray-700 dark:text-slate-400">{tool}</strong>
        </span>
      </div>
      {argsStr && (
        <div className="mt-1 ml-5 flex items-center gap-2 text-[10px] font-mono text-gray-500 dark:text-slate-400 bg-white dark:bg-[#252526] px-2 py-1 rounded border border-gray-200 dark:border-[#3e3e42] w-fit max-w-full">
          <Wrench size={10} className="opacity-50 flex-shrink-0" />
          <span className="truncate opacity-80">{argsStr}</span>
        </div>
      )}
    </div>
  );
};

const ToolBadge = React.memo(ToolBadgeComponent);

export default ToolBadge;