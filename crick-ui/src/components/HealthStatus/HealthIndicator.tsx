import React from 'react';
import { useHealth } from '@/hooks/useHealth';

export interface HealthIndicatorProps {
  className?: string;
}

const HealthIndicator: React.FC<HealthIndicatorProps> = ({ className }) => {
  const health = useHealth({
    autoStart: true,
  });

  const getStatusColor = () => {
    switch (health.status) {
      case 'online':
        return 'bg-emerald-500';
      case 'offline':
        return 'bg-red-500';
      case 'checking':
        return 'bg-amber-500 animate-pulse';
      default:
        return 'bg-slate-700';
    }
  };

  const getTooltip = () => {
    switch (health.status) {
      case 'online':
        return `Server: online\nLast check: ${health.formattedTimeSinceLastSuccess}\nVersion: ${health.version || 'unknown'}`;
      case 'offline':
        return `Server: offline\nErrors: ${health.errorCount}\nLast success: ${health.formattedTimeSinceLastSuccess}`;
      case 'checking':
        return `Checking server status...`;
      default:
        return `Server: ${health.status}`;
    }
  };

  return (
    <div
      className={`w-3 h-3 rounded-full cursor-help ${getStatusColor()} ${className}`}
      title={getTooltip()}
    />
  );
};

export default HealthIndicator;