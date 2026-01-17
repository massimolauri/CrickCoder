import React from 'react';
import { Calendar, Clock, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { useSessions } from '@/hooks/useSessions';

export interface SessionListProps {
  projectPath: string;
  onSelectSession?: (sessionId: string) => void;
  onNewSession?: () => void;
  selectedSessionId?: string | null;
  className?: string;
}

const SessionList: React.FC<SessionListProps> = ({
  projectPath,
  onSelectSession,
  onNewSession,
  selectedSessionId,
  className = '',
}) => {
  const sessions = useSessions({
    projectPath,
    autoLoad: true,
  });


  const parseDate = (dateValue: any): Date => {
    if (!dateValue) return new Date();
    if (typeof dateValue === 'number') return new Date(dateValue);
    if (typeof dateValue === 'string') return new Date(dateValue);
    if (dateValue instanceof Date) return dateValue;
    // Se è un oggetto, prova a estrarre timestamp
    try {
      const str = String(dateValue);
      return new Date(str);
    } catch {
      return new Date();
    }
  };

  const formatTime = (dateValue: any) => {
    const date = parseDate(dateValue);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (dateValue: any) => {
    const date = parseDate(dateValue);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  const getSummaryText = (summary: any): string | null => {
    // Se è stringa, ritorna anche se vuota (sarà gestita dal chiamante)
    if (typeof summary === 'string') return summary;
    // Se è null/undefined, ritorna null
    if (!summary) return null;
    if (typeof summary === 'object') {
      // Prova a estrarre testo da oggetto summary
      if (summary.text) return String(summary.text);
      if (summary.content) return String(summary.content);
      if (summary.summary) return String(summary.summary);
      // Altrimenti prova a stringificare
      try {
        return JSON.stringify(summary);
      } catch {
        return 'Object summary';
      }
    }
    return String(summary);
  };

  if (sessions.loading) {
    return (
      <div className={`p-4 text-sm text-slate-500 ${className}`}>
        Loading sessions...
      </div>
    );
  }

  if (sessions.error) {
    return (
      <div className={`p-4 text-sm text-red-400 ${className}`}>
        Error loading sessions: {sessions.error}
      </div>
    );
  }

  if (!sessions.hasSessions) {
    return (
      <div className={`p-6 text-center text-sm text-slate-500 ${className}`}>
        <p>No sessions found</p>
        <p className="text-xs mt-1">Start a conversation to create a session</p>
        {onNewSession && (
          <button
            onClick={onNewSession}
            className="mt-4 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#1f6feb]/10 hover:bg-[#1f6feb]/20 text-[#58a6ff] border border-[#1f6feb]/30 hover:border-[#1f6feb]/50 transition-colors text-sm font-medium mx-auto"
          >
            <Plus size={14} />
            New Session
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* New Session Button */}
      {onNewSession && (
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-full bg-[#1a73e8] hover:bg-[#1557b0] text-white shadow-lg shadow-blue-900/20 hover:shadow-xl hover:-translate-y-0.5 transition-all text-sm font-bold tracking-wide"
        >
          <Plus size={16} />
          NEW SESSION
        </button>
      )}

      <div className="px-4 py-2 text-[10px] font-bold text-crick-text-secondary uppercase tracking-widest">
        Recent Sessions ({sessions.sessionCount})
      </div>

      <div className="space-y-2">
        {sessions.sessions.map((session) => {
          const lastRequestText = getSummaryText(session.last_request);
          const showLastRequest = lastRequestText && lastRequestText.trim() !== '';
          const isSelected = selectedSessionId === session.session_id;

          return (
            <div
              key={session.session_id}
              className={`px-4 py-3 rounded-2xl cursor-pointer transition-all border group relative overflow-hidden ${isSelected
                ? 'bg-blue-50 dark:bg-blue-500/20 border-blue-200 dark:border-blue-500/30'
                : 'bg-transparent border-transparent hover:bg-gray-50 dark:hover:bg-white/5 hover:border-gray-100 dark:hover:border-[#3e3e42]'
                }`}
              onClick={() => onSelectSession?.(session.session_id)}
            >
              {isSelected && (
                <div className="absolute left-0 top-3 bottom-3 w-1 bg-crick-accent rounded-r-full" />
              )}

              <div className="flex items-center justify-between">
                <div className="flex items-center mb-1 flex-1 min-w-0 pl-2">
                  <span className={`text-sm truncate overflow-hidden transition-colors ${isSelected ? 'font-semibold text-blue-600 dark:text-blue-300' : 'font-medium text-crick-text-primary group-hover:text-crick-text-primary'}`}>
                    {getSummaryText(session.summary) || session.session_id.slice(0, 8)}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm('Are you sure you want to delete this session?')) {
                        sessions.deleteSession(session.session_id);
                      }
                    }}
                    className="p-1.5 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-all"
                    title="Delete session"
                  >
                    <Trash2 size={12} />
                  </button>
                  {isSelected && (
                    <ChevronRight size={14} className="text-crick-accent animate-in fade-in slide-in-from-left-1" />
                  )}
                </div>
              </div>

              <div className="mt-1 flex items-center gap-3 text-[10px] text-gray-500 dark:text-gray-400 pl-2 transition-opacity">
                <div className="flex items-center gap-1">
                  <Calendar size={10} />
                  <span>{session.updated_at_formatted ? session.updated_at_formatted.split(' ')[0] : formatDate(session.updated_at)}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock size={10} />
                  <span>{session.updated_at_formatted ? session.updated_at_formatted.split(' ')[1] : formatTime(session.updated_at)}</span>
                </div>
              </div>

              {showLastRequest && (
                <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400 truncate pl-2 opacity-80 group-hover:opacity-100 transition-opacity font-mono">
                  {lastRequestText}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SessionList;
