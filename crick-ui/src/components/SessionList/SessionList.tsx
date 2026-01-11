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
    <div className={`space-y-2 ${className}`}>
      {/* Bottone nuova sessione */}
      {onNewSession && (
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-[#1f6feb]/10 hover:bg-[#1f6feb]/20 text-[#58a6ff] border border-[#1f6feb]/30 hover:border-[#1f6feb]/50 transition-colors text-sm font-medium mb-2"
        >
          <Plus size={14} />
          New Session
        </button>
      )}
      <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
        Recent Sessions ({sessions.sessionCount})
      </div>
      {sessions.sessions.map((session) => {
        const lastRequestText = getSummaryText(session.last_request);
        const showLastRequest = lastRequestText && lastRequestText.trim() !== '';
        return (
          <div
            key={session.session_id}
            className={`px-3 py-3 rounded-lg cursor-pointer transition-all border group ${
              selectedSessionId === session.session_id
                ? 'bg-[#1f6feb]/20 border-[#1f6feb]/30 shadow-md'
                : 'bg-[#161b22] border-[#30363d] hover:bg-[#1f6feb]/10 hover:border-[#1f6feb]/20 shadow-sm'
            }`}
            onClick={() => onSelectSession?.(session.session_id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center mb-1 flex-1 min-w-0">
                <span className="text-sm font-medium text-slate-300 truncate overflow-hidden">
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
                  className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete session"
                >
                  <Trash2 size={12} />
                </button>
                {selectedSessionId === session.session_id && (
                  <ChevronRight size={14} className="text-[#58a6ff]" />
                )}
              </div>
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
              <div className="flex items-center gap-1">
                <Calendar size={12} />
                <span>{session.updated_at_formatted ? session.updated_at_formatted.split(' ')[0] : formatDate(session.updated_at)}</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock size={12} />
                <span>{session.updated_at_formatted ? session.updated_at_formatted.split(' ')[1] : formatTime(session.updated_at)}</span>
              </div>
            </div>
            {showLastRequest && (
              <div className="mt-2 text-xs text-slate-400 truncate">
                Last: {lastRequestText}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default SessionList;