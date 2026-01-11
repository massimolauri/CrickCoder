import { useState, useCallback, useEffect, useRef } from 'react';
import { sessionService } from '@/services/sessionService';
import type { Session } from '@/types/api.types';

/** Stato delle sessioni */
export interface SessionsState {
  sessions: Session[];
  loading: boolean;
  error: string | null;
  selectedSessionId: string | null;
}

/** Opzioni per useSessions */
export interface UseSessionsOptions {
  projectPath: string;
  autoLoad?: boolean;
  pollingInterval?: number;
  onSessionsLoaded?: (sessions: Session[]) => void;
  onError?: (error: Error) => void;
}

/**
 * Hook per la gestione delle sessioni
 */
export function useSessions(options: UseSessionsOptions) {
  const {
    projectPath,
    autoLoad = true,
    pollingInterval = 5000,
    onSessionsLoaded,
    onError,
  } = options;

  const [state, setState] = useState<SessionsState>({
    sessions: [],
    loading: false,
    error: null,
    selectedSessionId: sessionService.getCurrentSession(projectPath),
  });

  const isLoadingRef = useRef(false);

  /**
   * Carica le sessioni dal server
   */
  const loadSessions = useCallback(async (options?: { skipLoading?: boolean }) => {
    if (!projectPath) {
      setState(prev => ({ ...prev, error: 'No project path provided' }));
      return;
    }

    // Evita chiamate duplicate
    if (isLoadingRef.current) {
      return;
    }

    isLoadingRef.current = true;

    // Mostra loading solo se non skipLoading
    if (!options?.skipLoading) {
      setState(prev => ({ ...prev, loading: true, error: null }));
    }

    try {
      const result = await sessionService.listSessions(projectPath);

      if (result.success) {
        const sortedSessions = sessionService.sortSessionsByDate(result.data.sessions);

        // Aggiorna solo se i dati sono cambiati
        setState(prev => {
          // Confronta le sessioni attuali con quelle nuove
          const currentSessions = prev.sessions;
          const sessionsChanged = currentSessions.length !== sortedSessions.length ||
            currentSessions.some((session, index) =>
              session.session_id !== sortedSessions[index]?.session_id ||
              session.updated_at !== sortedSessions[index]?.updated_at
            );

          if (sessionsChanged) {
            onSessionsLoaded?.(sortedSessions);
            return {
              ...prev,
              sessions: sortedSessions,
              loading: false,
            };
          } else {
            // Dati invariati, mantieni stato corrente
            return prev.loading ? { ...prev, loading: false } : prev;
          }
        });
      } else {
        // Check if this is a network error from the API client
        const errorMessage = result.error.message;
        const errorMessageLower = errorMessage.toLowerCase();
        const isNetworkError = (
          errorMessageLower.includes('failed to fetch') ||
          errorMessageLower.includes('networkerror') ||
          errorMessageLower.includes('network error') ||
          errorMessageLower.includes('network request failed') ||
          errorMessageLower.includes('load failed') ||
          errorMessageLower.includes('request timeout') ||
          errorMessageLower.includes('when attempting to fetch resource')
        );

        if (isNetworkError && options?.skipLoading) {
          // Polling retry for network error: keep current state
          // Don't show error and don't change loading state
          console.debug('Server unreachable, will retry on next poll...');
        } else if (isNetworkError) {
          // First attempt failed with network error: keep loading
          // Don't show error, wait for next polling attempt
          setState(prev => ({
            ...prev,
            // Keep loading true, don't set error
            error: null
          }));
          console.debug('Server unreachable, keeping loading state...');
        } else {
          // Other type of error (not network)
          setState(prev => ({
            ...prev,
            loading: false,
            error: errorMessage,
          }));
          onError?.(new Error(errorMessage));
        }
      }
    } catch (error) {
      // This catch block handles unexpected errors (not network errors from API client)
      // Network errors are already handled in the else block above
      const errorMessage = error instanceof Error ? error.message : 'Failed to load sessions';
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }));
      onError?.(error instanceof Error ? error : new Error(errorMessage));
    } finally {
      isLoadingRef.current = false;
    }
  }, [projectPath, onSessionsLoaded, onError]);

  /**
   * Seleziona una sessione
   */
  const selectSession = useCallback((sessionId: string) => {
    setState(prev => ({ ...prev, selectedSessionId: sessionId }));
    sessionService.saveCurrentSession(projectPath, sessionId);
  }, [projectPath]);

  /**
   * Deseleziona la sessione corrente
   */
  const deselectSession = useCallback(() => {
    setState(prev => ({ ...prev, selectedSessionId: null }));
    sessionService.clearSession(projectPath);
  }, [projectPath]);

  /**
   * Aggiorna una sessione nella lista
   */
  const updateSession = useCallback((sessionId: string, updates: Partial<Session>) => {
    setState(prev => {
      const sessionIndex = prev.sessions.findIndex(s => s.session_id === sessionId);
      if (sessionIndex === -1) return prev;

      const updatedSessions = [...prev.sessions];
      updatedSessions[sessionIndex] = {
        ...updatedSessions[sessionIndex],
        ...updates,
      };

      return { ...prev, sessions: updatedSessions };
    });
  }, []);

  /**
   * Rimuove una sessione dalla lista (solo frontend)
   */
  const removeSession = useCallback((sessionId: string) => {
    setState(prev => ({
      ...prev,
      sessions: prev.sessions.filter(s => s.session_id !== sessionId),
    }));

    // Se la sessione rimossa è quella selezionata, deseleziona
    if (state.selectedSessionId === sessionId) {
      deselectSession();
    }
  }, [state.selectedSessionId, deselectSession]);

  /**
   * Cancella una sessione dal backend e dalla lista
   */
  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const result = await sessionService.deleteSession(sessionId, projectPath);

      if (result.success) {
        // Rimuovi la sessione dalla lista frontend
        removeSession(sessionId);
      } else {
        // Gestisci errore backend
        console.error('Failed to delete session:', result.error);
        // Potresti mostrare un toast o messaggio di errore qui
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  }, [projectPath, removeSession]);

  /**
   * Raggruppa le sessioni per data
   */
  const groupedSessions = sessionService.groupSessionsByDate(state.sessions);

  /**
   * Filtra le sessioni per tipo
   */
  const filterSessionsByType = useCallback((type: string) => {
    return state.sessions.filter(session => session.session_type === type);
  }, [state.sessions]);

  /**
   * Cerca sessioni per testo
   */
  const searchSessions = useCallback((query: string) => {
    const lowerQuery = query.toLowerCase();
    return state.sessions.filter(session =>
      session.session_id.toLowerCase().includes(lowerQuery) ||
      session.summary?.toLowerCase().includes(lowerQuery) ||
      session.last_request?.toLowerCase().includes(lowerQuery)
    );
  }, [state.sessions]);

  // Caricamento automatico
  useEffect(() => {
    if (autoLoad && projectPath) {
      loadSessions();
    }
  }, [autoLoad, projectPath, loadSessions]);

  // Polling automatico per aggiornare la lista sessioni
  useEffect(() => {
    if (!autoLoad || !projectPath || pollingInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      loadSessions({ skipLoading: true });
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [autoLoad, projectPath, pollingInterval, loadSessions]);

  // Aggiorna sessione selezionata dal localStorage
  useEffect(() => {
    if (projectPath) {
      const storedSessionId = sessionService.getCurrentSession(projectPath);
      if (storedSessionId && storedSessionId !== state.selectedSessionId) {
        setState(prev => ({ ...prev, selectedSessionId: storedSessionId }));
      }
    }
  }, [projectPath, state.selectedSessionId]);

  return {
    // Stato
    sessions: state.sessions,
    loading: state.loading,
    error: state.error,
    selectedSessionId: state.selectedSessionId,

    // Azioni
    loadSessions,
    selectSession,
    deselectSession,
    updateSession,
    removeSession,
    deleteSession,

    // Dati derivati
    groupedSessions,
    filterSessionsByType,
    searchSessions,

    // Helper
    hasSessions: state.sessions.length > 0,
    sessionCount: state.sessions.length,
    selectedSession: state.sessions.find(s => s.session_id === state.selectedSessionId),

    // Formattazione
    formatDate: sessionService.formatSessionDate,
  };
}

/**
 * Hook per il contatore delle sessioni
 */
export function useSessionCounter(projectPath: string) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!projectPath) {
      setCount(0);
      return;
    }

    const updateCount = async () => {
      try {
        const result = await sessionService.listSessions(projectPath);
        if (result.success) {
          setCount(result.data.count);
        }
      } catch {
        // Ignora errori
      }
    };

    updateCount();

    // Aggiorna ogni minuto
    const interval = setInterval(updateCount, 60000);
    return () => clearInterval(interval);
  }, [projectPath]);

  return count;
}

/**
 * Hook per la sessione corrente
 */
export function useCurrentSession(projectPath: string) {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (projectPath) {
      const current = sessionService.getCurrentSession(projectPath);
      setSessionId(current);
    }
  }, [projectPath]);

  const updateCurrentSession = useCallback((newSessionId: string) => {
    if (projectPath) {
      sessionService.saveCurrentSession(projectPath, newSessionId);
      setSessionId(newSessionId);
    }
  }, [projectPath]);

  const clearCurrentSession = useCallback(() => {
    if (projectPath) {
      sessionService.clearSession(projectPath);
      setSessionId(null);
    }
  }, [projectPath]);

  return {
    sessionId,
    updateCurrentSession,
    clearCurrentSession,
    hasSession: sessionId !== null,
  };
}