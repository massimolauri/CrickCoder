import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { chatService } from '@/services/chatService';
import { sessionService } from '@/services/sessionService';
import { llmSettingsStorage } from '@/utils/storage';
import type { ChatMessage, ChatEvent, LLMSettings } from '@/types/api.types';

/** Recupera agentId da localStorage per una sessione */
function getAgentIdForSession(sessionId: string | null): "ARCHITECT" | "CODER" {
  if (!sessionId) return "ARCHITECT";
  const key = `crick_agent_id_${sessionId}`;
  const stored = localStorage.getItem(key);
  return (stored === "ARCHITECT" || stored === "CODER") ? stored : "ARCHITECT";
}

/** Salva agentId in localStorage per una sessione */
function saveAgentIdForSession(sessionId: string | null, value: "ARCHITECT" | "CODER"): void {
  if (!sessionId) return;
  const key = `crick_agent_id_${sessionId}`;
  localStorage.setItem(key, value);
}

/** Stato della chat */
export interface ChatState {
  messages: ChatMessage[];
  streaming: boolean;
  currentSessionId: string | null;
  error: string | null;
  selectedAgentId: "ARCHITECT" | "CODER";
  llmSettings: LLMSettings;
  pausedRunId: string | null;
  pausedAgentName: string | null;
  pausedTool: string | null;
}

/** Opzioni per useChat */
export interface UseChatOptions {
  projectPath: string;
  initialMessages?: ChatMessage[];
  llmSettings?: LLMSettings;
  onNewMessage?: (message: ChatMessage) => void;
  onStreamStart?: () => void;
  onStreamEnd?: () => void;
  onError?: (error: Error) => void;
}

/**
 * Hook per la gestione della chat con streaming
 */
export function useChat(options: UseChatOptions) {
  const {
    projectPath,
    initialMessages = [],
    onNewMessage,
    onStreamStart,
    onStreamEnd,
    onError,
  } = options;

  // Stati separati per evitare re-rendering completi
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [streaming, setStreaming] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(
    sessionService.getCurrentSession(projectPath)
  );
  const [error, setError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentIdState] = useState<"ARCHITECT" | "CODER">(
    getAgentIdForSession(sessionService.getCurrentSession(projectPath))
  );
  const [llmSettings, setLlmSettings] = useState<LLMSettings>(
    options.llmSettings || llmSettingsStorage.get() || {
      provider: "DeepSeek",
      model_id: "deepseek-chat",
      api_key: "",
      temperature: 0.2,
    }
  );
  const [pausedRunId, setPausedRunId] = useState<string | null>(null);
  const [pausedAgentName, setPausedAgentName] = useState<string | null>(null);
  const [pausedTool, setPausedTool] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  /** Aggiorna selectedAgentId per la sessione corrente */
  const setSelectedAgentId = useCallback((value: "ARCHITECT" | "CODER") => {
    saveAgentIdForSession(currentSessionId, value);
    setSelectedAgentIdState(value);
  }, [currentSessionId]);

  // Inizializza la sessione se non esiste
  useEffect(() => {
    if (projectPath && !currentSessionId) {
      const newSessionId = sessionService.generateLocalSessionId();
      setCurrentSessionId(newSessionId);
      sessionService.saveCurrentSession(projectPath, newSessionId);
    }
  }, [projectPath, currentSessionId]);

  // Aggiorna selectedAgentId quando cambia la sessione
  useEffect(() => {
    setSelectedAgentIdState(getAgentIdForSession(currentSessionId));
    setPausedRunId(null);
    setPausedAgentName(null);
    setPausedTool(null);
  }, [currentSessionId]);

  // Sincronizza llmSettings quando le props cambiano
  useEffect(() => {
    const newLlmSettings = options.llmSettings || llmSettingsStorage.get() || {
      provider: "DeepSeek",
      model_id: "deepseek-chat",
      api_key: "",
      temperature: 0.2,
    };

    if (JSON.stringify(llmSettings) !== JSON.stringify(newLlmSettings)) {
      setLlmSettings(newLlmSettings);
    }
  }, [options.llmSettings, llmSettings]);

  /**
   * Invia un messaggio
   */
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || !projectPath) {
      return;
    }

    // Cancella stream precedente
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();

    // Aggiungi messaggio utente
    const userMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content,
    };

    setMessages(prev => [...prev, userMessage]);
    setStreaming(true);
    setError(null);
    setPausedRunId(null);
    setPausedAgentName(null);
    setPausedTool(null);

    onNewMessage?.(userMessage);
    onStreamStart?.();

    // Crea messaggio AI vuoto
    const aiMessageId = Date.now() + 1;
    const aiMessage: ChatMessage = {
      id: aiMessageId,
      role: 'assistant',
      timeline: [],
    };

    setMessages(prev => [...prev, aiMessage]);

    onNewMessage?.(aiMessage);

    // Gestisci eventi streaming
    const handleEvent = (event: ChatEvent) => {
      // Gestione eventi 'paused' separata
      if (event.type === 'paused') {
        setPausedRunId(event.run_id);
        setPausedAgentName(event.agent_name);
        setPausedTool(event.tool);
        return;
      }

      // Aggiorna il messaggio AI
      setMessages(prevMessages => {
        const aiMessageIndex = prevMessages.findIndex(m => m.id === aiMessageId);
        if (aiMessageIndex === -1) return prevMessages;

        const messageToUpdate = prevMessages[aiMessageIndex];
        const timeline = [...(messageToUpdate.timeline || [])];
        const lastIndex = timeline.length - 1;
        const lastItem = timeline[lastIndex];

        switch (event.type) {
          case 'content':
            if (lastItem && lastItem.type === 'text' && lastItem.agent === event.agent) {
              // Continua testo esistente
              timeline[lastIndex] = {
                ...lastItem,
                content: lastItem.content + event.content,
              };
            } else {
              // Nuovo blocco testo
              timeline.push({
                type: 'text',
                content: event.content,
                agent: event.agent || 'System',
              });
            }
            break;

          case 'tool_start':
            timeline.push({
              type: 'tool',
              tool: event.tool,
              args: event.args,
              status: 'running',
              agent: event.agent,
            });
            break;

          case 'tool_end':
            const isTerminal = event.result && (
              event.result.includes('Exit Code') ||
              event.tool.includes('shell') ||
              event.tool.includes('build')
            );

            if (lastItem && lastItem.type === 'tool' && lastItem.status === 'running') {
              if (isTerminal) {
                // Converti in output terminale
                timeline[lastIndex] = {
                  type: 'terminal',
                  command: event.tool,
                  output: event.result,
                  agent: event.agent,
                };
              } else {
                // Segna come completato
                timeline[lastIndex] = {
                  ...lastItem,
                  status: 'completed',
                };
              }
            }
            break;

          case 'error':
            timeline.push({
              type: 'text',
              content: `Error: ${event.message}`,
              agent: 'System',
            });
            break;
        }

        // Crea nuovo array di messaggi con l'aggiornamento
        const updatedMessages = [...prevMessages];
        updatedMessages[aiMessageIndex] = {
          ...messageToUpdate,
          timeline,
        };

        return updatedMessages;
      });
    };

    const handleDone = () => {
      setStreaming(false);
      onStreamEnd?.();
      abortControllerRef.current = null;
    };

    const handleError = (error: Error) => {
      setStreaming(false);
      setError(error.message);

      onError?.(error);
      abortControllerRef.current = null;
    };

    try {
      await chatService.sendMessage(
        projectPath,
        content,
        {
          sessionId: currentSessionId,
          agentId: selectedAgentId,
          llmSettings: llmSettings,
          autoApproval: true,
          onEvent: handleEvent,
          onDone: handleDone,
          onError: handleError,
          signal: abortControllerRef.current.signal,
        }
      );
    } catch (error) {
      handleError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [projectPath, currentSessionId, selectedAgentId, llmSettings, onNewMessage, onStreamStart, onStreamEnd, onError]);

  /**
   * Cancella la conversazione corrente
   */
  const clearConversation = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setMessages([]);
    setStreaming(false);
    setError(null);
    setPausedRunId(null);
    setPausedAgentName(null);
    setPausedTool(null);

    // Genera nuova sessione
    if (projectPath) {
      const newSessionId = sessionService.generateLocalSessionId();
      setCurrentSessionId(newSessionId);
      sessionService.saveCurrentSession(projectPath, newSessionId);
    }
  }, [projectPath]);

  /**
   * Cambia sessione
   */
  const switchSession = useCallback(async (sessionId: string) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // Clear current messages immediately for responsive UI
    setMessages([]);
    setStreaming(false);
    setCurrentSessionId(sessionId);
    setError(null);
    setPausedRunId(null);
    setPausedAgentName(null);
    setPausedTool(null);

    if (projectPath) {
      sessionService.saveCurrentSession(projectPath, sessionId);

      // Load session history from backend
      try {
        const result = await sessionService.loadSessionHistory(sessionId, projectPath);
        if (result.success && result.data?.messages) {
          setMessages(result.data.messages);
        } else if (!result.success) {
          console.error('Failed to load session history:', result.error?.message);
          // Keep messages empty - session might be new or have no history
        }
      } catch (error) {
        console.error('Error loading session history:', error);
        // Silently fail - session might be new
      }
    }
  }, [projectPath]);

  /**
   * Continua sessione esistente
   */
  const continueSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);

    if (projectPath) {
      sessionService.saveCurrentSession(projectPath, sessionId);
    }
  }, [projectPath]);

  /**
   * Cancella lo stream corrente
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;

      setStreaming(false);
      onStreamEnd?.();
    }
  }, [onStreamEnd]);

  /**
   * Continua una chat in pausa dopo conferma utente
   */
  const continueRun = useCallback(async (decision: 'approve' | 'reject' | 'allow' | 'block', feedback?: string | null) => {
    if (!pausedRunId || !pausedAgentName) {
      return;
    }

    // Trova l'ultimo messaggio AI per aggiornare la timeline
    const lastAiMessage = [...messages].reverse().find(m => m.role === 'assistant');
    const aiMessageId = lastAiMessage?.id || Date.now();

    // Se non esiste un messaggio AI, ne creiamo uno nuovo (caso edge)
    if (!lastAiMessage) {
      const newAiMessage: ChatMessage = {
        id: aiMessageId,
        role: 'assistant',
        timeline: [],
      };
      setMessages(prev => [...prev, newAiMessage]);
    }

    // Cancella stream precedente se presente
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    abortControllerRef.current = new AbortController();

    setStreaming(true);

    // Gestione eventi (stessa logica di sendMessage)
    const handleEvent = (event: ChatEvent) => {
      // Gestione eventi 'paused' separata
      if (event.type === 'paused') {
        setPausedRunId(event.run_id);
        setPausedAgentName(event.agent_name);
        setPausedTool(event.tool);
        return;
      }

      // Aggiorna il messaggio AI
      setMessages(prevMessages => {
        const aiMessageIndex = prevMessages.findIndex(m => m.id === aiMessageId);
        if (aiMessageIndex === -1) return prevMessages;

        const messageToUpdate = prevMessages[aiMessageIndex];
        const timeline = [...(messageToUpdate.timeline || [])];
        const lastIndex = timeline.length - 1;
        const lastItem = timeline[lastIndex];

        switch (event.type) {
          case 'content':
            if (lastItem && lastItem.type === 'text' && lastItem.agent === event.agent) {
              // Continua testo esistente
              timeline[lastIndex] = {
                ...lastItem,
                content: lastItem.content + event.content,
              };
            } else {
              // Nuovo blocco testo
              timeline.push({
                type: 'text',
                content: event.content,
                agent: event.agent || 'System',
              });
            }
            break;

          case 'tool_start':
            timeline.push({
              type: 'tool',
              tool: event.tool,
              args: event.args,
              status: 'running',
              agent: event.agent,
            });
            break;

          case 'tool_end':
            const isTerminal = event.result && (
              event.result.includes('Exit Code') ||
              event.tool.includes('shell') ||
              event.tool.includes('build')
            );

            if (lastItem && lastItem.type === 'tool' && lastItem.status === 'running') {
              if (isTerminal) {
                timeline[lastIndex] = {
                  type: 'terminal',
                  command: event.tool,
                  output: event.result,
                  agent: event.agent,
                };
              } else {
                timeline[lastIndex] = {
                  ...lastItem,
                  status: 'completed',
                };
              }
            }
            break;

          case 'error':
            timeline.push({
              type: 'text',
              content: `Error: ${event.message}`,
              agent: 'System',
            });
            break;
        }

        // Crea nuovo array di messaggi con l'aggiornamento
        const updatedMessages = [...prevMessages];
        updatedMessages[aiMessageIndex] = {
          ...messageToUpdate,
          timeline,
        };

        return updatedMessages;
      });
    };

    const handleDone = () => {
      setStreaming(false);
      setPausedRunId(null);
      onStreamEnd?.();
      abortControllerRef.current = null;
    };

    const handleError = (error: Error) => {
      setStreaming(false);
      setError(error.message);
      setPausedRunId(null);

      onError?.(error);
      abortControllerRef.current = null;
    };

    try {
      await chatService.continueRun(
        pausedRunId,
        currentSessionId || '',
        projectPath,
        decision,
        feedback,
        {
          onEvent: handleEvent,
          onDone: handleDone,
          onError: handleError,
          signal: abortControllerRef.current.signal,
        }
      );
    } catch (error) {
      handleError(error instanceof Error ? error : new Error(String(error)));
    }
  }, [pausedRunId, pausedAgentName, currentSessionId, projectPath, messages, onStreamEnd, onError]);

  // Memoizzare valori calcolati
  const hasMessages = useMemo(() => messages.length > 0, [messages]);
  const lastMessage = useMemo(() => messages[messages.length - 1], [messages]);

  return {
    // Stato
    messages,
    streaming,
    currentSessionId,
    error,
    selectedAgentId,
    llmSettings,
    pausedRunId,
    pausedAgentName,
    pausedTool,

    // Azioni
    sendMessage,
    clearConversation,
    switchSession,
    continueSession,
    cancelStream,
    setSelectedAgentId,
    continueRun,

    // Helper
    hasMessages,
    lastMessage,
  };
}

/**
 * Hook per il calcolo delle statistiche della chat
 */
export function useChatStats(messages: ChatMessage[]) {
  const stats = useRef({
    totalMessages: 0,
    userMessages: 0,
    aiMessages: 0,
    totalTokens: 0, // Stima
    toolExecutions: 0,
    terminalOutputs: 0,
  });

  // Ricalcola statistiche quando i messaggi cambiano
  useEffect(() => {
    let userMessages = 0;
    let aiMessages = 0;
    let toolExecutions = 0;
    let terminalOutputs = 0;

    messages.forEach(message => {
      if (message.role === 'user') userMessages++;
      if (message.role === 'assistant') aiMessages++;

      if (message.timeline) {
        message.timeline.forEach(item => {
          if (item.type === 'tool') toolExecutions++;
          if (item.type === 'terminal') terminalOutputs++;
        });
      }
    });

    stats.current = {
      totalMessages: messages.length,
      userMessages,
      aiMessages,
      totalTokens: Math.floor(
        messages.reduce((acc, msg) => acc + (msg.content?.length || 0), 0) / 4
      ), // Stima approssimativa
      toolExecutions,
      terminalOutputs,
    };
  }, [messages]);

  return stats.current;
}