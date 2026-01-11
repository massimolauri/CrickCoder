import React, { useMemo } from 'react';
import { getAgentConfig } from '@/utils/agentUtils';

export interface AgentHeaderProps {
  name: string;
}

const AgentHeaderComponent: React.FC<AgentHeaderProps> = ({ name }) => {
  const config = useMemo(() => getAgentConfig(name), [name]);

  return (
    <div
      className={`flex items-center gap-2 mt-4 mb-1 self-start px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border bg-opacity-10 ${config.border} ${config.bg} ${config.color}`}
    >
      {config.icon} {name}
    </div>
  );
};

const AgentHeader = React.memo(AgentHeaderComponent);
export default AgentHeader;