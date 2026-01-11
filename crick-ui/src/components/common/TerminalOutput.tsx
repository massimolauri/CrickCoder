import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { getAgentConfig } from '@/utils/agentUtils';

export interface TerminalOutputProps {
  command?: string;
  output?: string;
  agent?: string;
}

const TerminalOutputComponent: React.FC<TerminalOutputProps> = ({ command, output, agent }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const isError = useMemo(() =>
    output?.includes("FAIL") || output?.includes("Error") || output?.includes("Exception"),
    [output]
  );

  const config = useMemo(() => getAgentConfig(agent), [agent]);

  return (
    <div className="my-3 font-mono text-xs rounded-md border border-[#30363d] bg-black overflow-hidden shadow-lg animate-in fade-in slide-in-from-left-2">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors ${isError ? 'bg-red-900/20 text-red-400 border-b border-red-900/30' : 'bg-[#161b22] text-slate-400 hover:text-slate-200 border-b border-[#30363d]'}`}
      >
        <span className={config.color}>{config.icon}</span>
        <span className="font-bold truncate">$ {command || "Process Output"}</span>
        <div className="ml-auto opacity-50">{isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</div>
      </div>
      {isExpanded && (
        <div className={`p-3 overflow-x-auto max-h-80 scrollbar-thin scrollbar-thumb-slate-700 ${isError ? 'text-red-300' : 'text-emerald-300'}`}>
          <pre className="whitespace-pre-wrap">{output || "Done."}</pre>
        </div>
      )}
    </div>
  );
};

const TerminalOutput = React.memo(TerminalOutputComponent);
export default TerminalOutput;