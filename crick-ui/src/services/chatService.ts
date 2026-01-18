import { buildChatBody, buildContinueBody } from './apiClient';
import type { ChatEvent, EventCallback, LLMSettings } from '@/types/api.types';

/** Opzioni per invio messaggio */
export interface SendMessageOptions {
  sessionId?: string | null;
  agentId?: "ARCHITECT" | "CODER" | "PLANNER";
  llmSettings?: LLMSettings;
  autoApproval?: boolean;
  onEvent?: EventCallback;
  onDone?: () => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
}

/**
 * Servizio per la chat con streaming SSE
 */
export class ChatService {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
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
      onEvent,
      onDone,
      onError,
      signal,
    } = options;

    try {
      const body = buildChatBody(message, projectPath, sessionId, agentId, llmSettings, autoApproval ?? true);

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
        case 'content':
          if (typeof parsed.content !== 'string' || typeof parsed.agent !== 'string') {
            throw new Error('Invalid content event');
          }
          return {
            type: 'content',
            content: parsed.content,
            agent: parsed.agent,
          };

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