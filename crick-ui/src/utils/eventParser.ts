import type { ChatEvent } from '@/types/api.types';

/**
 * Parser per eventi SSE del chat stream
 */

/** Opzioni di parsing */
export interface ParseOptions {
  strict?: boolean;
  onError?: (error: Error, rawData: string) => void;
}

/**
 * Parsa una stringa di dati SSE in un evento chat
 */
export function parseSSEEvent(
  rawData: string,
  options: ParseOptions = {}
): ChatEvent | null {
  const { strict = true, onError } = options;

  if (!rawData.trim()) {
    return null;
  }

  // Rimuovi prefisso "data: " se presente
  const data = rawData.startsWith('data: ')
    ? rawData.substring(6).trim()
    : rawData.trim();

  // Controlla evento speciale [DONE]
  if (data === '[DONE]') {
    // Non è un evento chat, è un marker di fine stream
    return null;
  }

  try {
    const parsed = JSON.parse(data);
    return validateAndNormalizeEvent(parsed, strict);

  } catch (error) {
    const parseError = error instanceof Error ? error : new Error(String(error));

    if (strict) {
      onError?.(parseError, rawData);
      throw parseError;
    }

    onError?.(parseError, rawData);
    return null;
  }
}

/**
 * Valida e normalizza un evento parsato
 */
function validateAndNormalizeEvent(
  parsed: any,
  strict: boolean
): ChatEvent {
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Invalid event: not an object');
  }

  if (!parsed.type || typeof parsed.type !== 'string') {
    throw new Error('Invalid event: missing or invalid type');
  }

  switch (parsed.type) {
    case 'content':
    case 'text': // Supporta anche 'text' per compatibilità
      if (strict && (typeof parsed.content !== 'string' || typeof parsed.agent !== 'string')) {
        throw new Error('Invalid content event: missing content or agent');
      }
      return {
        type: 'content',
        content: parsed.content || '',
        agent: parsed.agent || 'System',
      };

    case 'tool_start':
      if (strict && (typeof parsed.tool !== 'string' || typeof parsed.agent !== 'string')) {
        throw new Error('Invalid tool_start event: missing tool or agent');
      }
      return {
        type: 'tool_start',
        agent: parsed.agent || 'System',
        tool: parsed.tool || 'unknown',
        args: parsed.args || {},
      };

    case 'tool_end':
      if (strict && (typeof parsed.tool !== 'string' || typeof parsed.agent !== 'string')) {
        throw new Error('Invalid tool_end event: missing tool or agent');
      }
      return {
        type: 'tool_end',
        agent: parsed.agent || 'System',
        tool: parsed.tool || 'unknown',
        result: parsed.result || '',
      };

    case 'error':
      if (strict && typeof parsed.message !== 'string') {
        throw new Error('Invalid error event: missing message');
      }
      return {
        type: 'error',
        message: parsed.message || 'Unknown error',
      };

    default:
      if (strict) {
        throw new Error(`Unknown event type: ${parsed.type}`);
      }
      // In modalità non strict, ritorna un evento errore generico
      return {
        type: 'error',
        message: `Unknown event type: ${parsed.type}`,
      };
  }
}

/**
 * Processa uno stream SSE completo
 */
export async function processSSEStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: ChatEvent) => void,
  onDone?: () => void,
  onError?: (error: Error) => void,
  options: ParseOptions = {}
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const events = extractCompleteEvents(buffer);

      // Aggiorna buffer con dati incompleti rimanenti
      buffer = events.remainingBuffer;

      for (const eventData of events.completeEvents) {
        try {
          const event = parseSSEEvent(eventData, options);
          if (event) {
            onEvent(event);
          } else if (eventData.includes('[DONE]')) {
            onDone?.();
            return;
          }
        } catch (error) {
          onError?.(error instanceof Error ? error : new Error(String(error)));
        }
      }
    }

    // Processa eventuali dati rimanenti
    if (buffer.trim()) {
      const events = extractCompleteEvents(buffer);
      for (const eventData of events.completeEvents) {
        try {
          const event = parseSSEEvent(eventData, options);
          if (event) {
            onEvent(event);
          }
        } catch (error) {
          onError?.(error instanceof Error ? error : new Error(String(error)));
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
 * Estrae eventi completi dal buffer SSE
 */
function extractCompleteEvents(buffer: string): {
  completeEvents: string[];
  remainingBuffer: string;
} {
  const lines = buffer.split('\n\n');
  const completeEvents: string[] = [];
  let remainingBuffer = '';

  // L'ultimo elemento potrebbe essere incompleto
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (i === lines.length - 1 && !line.includes('\n\n')) {
      // Ultima linea, potrebbe essere incompleta
      remainingBuffer = line;
    } else if (line.trim()) {
      completeEvents.push(line);
    }
  }

  return { completeEvents, remainingBuffer };
}

/**
 * Crea un mock stream per testing
 */
export function createMockSSEStream(
  events: ChatEvent[],
  options: {
    delayBetweenEvents?: number;
    includeDone?: boolean;
  } = {}
): ReadableStream<Uint8Array> {
  const { delayBetweenEvents = 0, includeDone = true } = options;

  return new ReadableStream({
    async start(controller) {
      for (const event of events) {
        if (delayBetweenEvents > 0) {
          await new Promise(resolve => setTimeout(resolve, delayBetweenEvents));
        }

        const data = `data: ${JSON.stringify(event)}\n\n`;
        controller.enqueue(new TextEncoder().encode(data));
      }

      if (includeDone) {
        controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'));
      }

      controller.close();
    },
  });
}

/**
 * Verifica se un evento indica output da terminale
 */
export function isTerminalOutput(event: ChatEvent): boolean {
  if (event.type !== 'tool_end') return false;

  const result = event.result.toLowerCase();
  return (
    result.includes('exit code') ||
    result.includes('shell') ||
    result.includes('build') ||
    result.includes('command') ||
    result.includes('error') ||
    result.includes('fail')
  );
}

/**
 * Estrae informazioni riassuntive da un evento
 */
export function getEventSummary(event: ChatEvent): {
  type: string;
  agent: string;
  summary: string;
} {
  switch (event.type) {
    case 'content':
      return {
        type: 'content',
        agent: event.agent,
        summary: event.content.substring(0, 100) + (event.content.length > 100 ? '...' : ''),
      };

    case 'tool_start':
      return {
        type: 'tool',
        agent: event.agent,
        summary: `${event.tool} started`,
      };

    case 'tool_end':
      return {
        type: 'tool',
        agent: event.agent,
        summary: `${event.tool} completed`,
      };

    case 'error':
      return {
        type: 'error',
        agent: 'System',
        summary: event.message,
      };

    default:
      return {
        type: 'unknown',
        agent: 'System',
        summary: 'Unknown event',
      };
  }
}