import { buildChatBody, buildContinueBody } from './apiClient';
import type { ChatEvent, EventCallback, LLMSettings } from '@/types/api.types';

/** Opzioni per invio messaggio */
export interface SendMessageOptions {
  sessionId?: string | null;
  agentId?: "ARCHITECT" | "CODER" | "PLANNER";
  llmSettings?: LLMSettings;
  autoApproval?: boolean;
  selectedThemeId?: string | null;
  onEvent?: EventCallback;
  onDone?: () => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
}

// Extend global Window interface
declare global {
  interface Window {
    CRICK_CONFIG?: {
      apiUrl: string;
    };
  }
}

export class ChatService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    if (baseUrl) {
      this.baseUrl = baseUrl;
    } else if (typeof window !== 'undefined' && window.CRICK_CONFIG?.apiUrl) {
      this.baseUrl = window.CRICK_CONFIG.apiUrl;
    } else {
      this.baseUrl = 'http://localhost:8000';
    }
  }

  /**
   * Invia un messaggio e restituisce uno stream di eventi SSE
   */
  async sendMessage(
    projectPath: string,
    message: string,
    options: SendMessageOptions = {}
  ): Promise<void> {
    const {
      sessionId,
      agentId,
      llmSettings,
      autoApproval,
      selectedThemeId,
      onEvent,
      onDone,
      onError,
      signal,
    } = options;

    try {
      const body = buildChatBody(message, projectPath, sessionId, agentId, llmSettings, autoApproval ?? true, selectedThemeId);

      const response = await fetch(`${this.baseUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      await this.processSSEStream(response.body, onEvent, onDone, onError);

    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        // Richiesta cancellata, non è un errore
        return;
      }

      onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Continua una chat in pausa dopo conferma utente
   */
  async continueRun(
    runId: string,
    sessionId: string,
    projectPath: string,
    decision: 'approve' | 'reject' | 'allow' | 'block',
    feedback?: string | null,
    options: { onEvent?: EventCallback, onDone?: () => void, onError?: (error: Error) => void, signal?: AbortSignal } = {}
  ): Promise<void> {
    const { onEvent, onDone, onError, signal } = options;

    try {
      const body = buildContinueBody(runId, sessionId, projectPath, decision, feedback);

      const response = await fetch(`${this.baseUrl}/api/chat/continue`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      await this.processSSEStream(response.body, onEvent, onDone, onError);

    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        // Richiesta cancellata, non è un errore
        return;
      }

      onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Esegue l'undo delle modifiche di un run specifico
   */
  async undoRun(runId: string, sessionId: string, projectPath: string, files?: string[]): Promise<void> {
    const params = new URLSearchParams({
      session_id: sessionId,
      project_path: projectPath
    });

    // If files are provided, send them in body
    const options: RequestInit = {
      method: 'POST'
    };

    if (files && files.length > 0) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify({ files });
    }

    const response = await fetch(`${this.baseUrl}/api/runs/${runId}/undo?${params.toString()}`, options);

    if (!response.ok) {
      throw new Error(`Undo failed: ${response.statusText}`);
    }
  }

  /**
   * Ottiene la lista dei file modificati in un run
   */
  async getRunFiles(runId: string, sessionId: string, projectPath: string): Promise<string[]> {
    const params = new URLSearchParams({
      session_id: sessionId,
      project_path: projectPath
    });

    const response = await fetch(`${this.baseUrl}/api/runs/${runId}/files?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`Failed to load modified files: ${response.statusText}`);
    }

    const data = await response.json();
    return data.files || [];
  }

  /**
   * Ottiene i diff per una lista di file
   */
  async getDiffs(files: string[], runId: string, sessionId: string, projectPath: string): Promise<Record<string, string>> {
    const params = new URLSearchParams({
      run_id: runId,
      session_id: sessionId,
      project_path: projectPath
    });

    const response = await fetch(`${this.baseUrl}/api/files/diff?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(files)
    });

    if (!response.ok) {
      throw new Error(`Failed to load diffs: ${response.statusText}`);
    }

    const data = await response.json();
    return data.diffs || {};
  }

  // ... existing private methods ...

  /**
   * Processa uno stream SSE
   */
  private async processSSEStream(
    readableStream: ReadableStream<Uint8Array>,
    onEvent?: EventCallback,
    onDone?: () => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    const reader = readableStream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');

        // Mantieni l'ultimo chunk incompleto nel buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          if (line.startsWith('data: ')) {
            const data = line.replace('data: ', '').trim();

            if (data === '[DONE]') {
              onDone?.();
              return;
            }

            try {
              const event = this.parseEvent(data);
              onEvent?.(event);
            } catch (parseError) {
              console.error('Error parsing SSE event:', parseError, 'Data:', data);
              onError?.(new Error(`Failed to parse event: ${parseError}`));
            }
          }
        }
      }

      // Processa eventuali dati rimanenti nel buffer
      if (buffer.trim()) {
        const lines = buffer.split('\n\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.replace('data: ', '').trim();
            if (data === '[DONE]') {
              onDone?.();
              return;
            }
            try {
              const event = this.parseEvent(data);
              onEvent?.(event);
            } catch (parseError) {
              console.error('Error parsing SSE event:', parseError);
            }
          }
        }
      }

      onDone?.();

    } catch (error) {
      onError?.(error instanceof Error ? error : new Error(String(error)));
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Parsa un evento SSE JSON
   */
  private parseEvent(data: string): ChatEvent {
    try {
      const parsed = JSON.parse(data);

      // Validazione base del tipo evento
      if (!parsed.type || typeof parsed.type !== 'string') {
        throw new Error('Invalid event: missing type');
      }

      // Mappa tipo evento al tipo TypeScript corrispondente
      switch (parsed.type) {
        case 'meta':
          return {
            type: 'meta',
            shadow_run_id: parsed.shadow_run_id,
            agent: parsed.agent || 'System'
          };

        case 'content':
          if (typeof parsed.content !== 'string' || typeof parsed.agent !== 'string') {
            throw new Error('Invalid content event');
          }
          return {
            type: 'content',
            content: parsed.content,
            agent: parsed.agent,
          };

        // ... other cases unchanged ...
        case 'tool_start':
          if (typeof parsed.tool !== 'string' || typeof parsed.agent !== 'string') {
            throw new Error('Invalid tool_start event');
          }
          return {
            type: 'tool_start',
            agent: parsed.agent,
            tool: parsed.tool,
            args: parsed.args || {},
          };

        case 'tool_end':
          if (typeof parsed.tool !== 'string' || typeof parsed.agent !== 'string') {
            throw new Error('Invalid tool_end event');
          }
          return {
            type: 'tool_end',
            agent: parsed.agent,
            tool: parsed.tool,
            result: parsed.result || '',
          };

        case 'error':
          if (typeof parsed.message !== 'string') {
            throw new Error('Invalid error event');
          }
          return {
            type: 'error',
            message: parsed.message,
          };

        case 'paused':
          if (typeof parsed.run_id !== 'string' || typeof parsed.agent_name !== 'string' || typeof parsed.tool !== 'string') {
            throw new Error('Invalid paused event: missing required fields');
          }
          return {
            type: 'paused',
            run_id: parsed.run_id,
            agent_name: parsed.agent_name,
            tool: parsed.tool,
          };

        default:
          throw new Error(`Unknown event type: ${parsed.type}`);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error(`Invalid JSON: ${data}`);
      }
      throw error;
    }
  }

  /**
   * Crea un segnale di abort per cancellare lo stream
   */
  createAbortController(): AbortController {
    return new AbortController();
  }
}

/** Istanza globale del servizio chat */
export const chatService = new ChatService();