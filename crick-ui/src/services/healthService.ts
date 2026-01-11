import { apiClient } from './apiClient';
import type { HealthResponse, ApiResult } from '@/types/api.types';

/** Configurazione health check */
export interface HealthCheckConfig {
  interval?: number; // ms tra i check
  timeout?: number; // timeout per ogni check
  retryCount?: number; // tentativi prima di considerare offline
}

/** Stato del monitoraggio */
import type { HealthMonitorState } from '@/types/api.types';

/** Callback per cambiamenti di stato */
export type HealthStatusCallback = (state: HealthMonitorState) => void;

/**
 * Servizio per health check e monitoraggio server
 */
export class HealthService {
  private config: Required<HealthCheckConfig>;
  private state: HealthMonitorState;
  private callbacks: HealthStatusCallback[] = [];
  private checkInterval: NodeJS.Timeout | null = null;
  private isChecking = false;

  constructor(config: HealthCheckConfig = {}) {
    this.config = {
      interval: 30000, // 30 secondi
      timeout: 10000,  // 10 secondi
      retryCount: 3,
      ...config,
    };

    this.state = {
      status: 'checking',
      lastCheck: null,
      lastSuccess: null,
      errorCount: 0,
      version: null,
      service: null,
    };
  }

  /**
   * Avvia il monitoraggio periodico
   */
  startMonitoring(): void {
    if (this.checkInterval) {
      this.stopMonitoring();
    }

    // Prima verifica immediata
    this.checkHealth();

    // Verifica periodica
    this.checkInterval = setInterval(() => {
      this.checkHealth();
    }, this.config.interval);
  }

  /**
   * Ferma il monitoraggio
   */
  stopMonitoring(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  /**
   * Esegue un singolo health check
   */
  async checkHealth(): Promise<ApiResult<HealthResponse>> {
    if (this.isChecking) {
      return { success: false, error: { message: 'Check already in progress' } };
    }

    this.isChecking = true;
    this.updateState({ lastCheck: Date.now() });

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

      const result = await apiClient.get<HealthResponse>('/health', {}, {
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (result.success) {
        this.handleSuccess(result.data);
        return result;
      } else {
        this.handleError(result.error);
        return result;
      }

    } catch (error) {
      this.handleError({
        message: error instanceof Error ? error.message : String(error),
      });
      return {
        success: false,
        error: {
          message: 'Network error',
          details: error,
        },
      };
    } finally {
      this.isChecking = false;
    }
  }

  /**
   * Gestisce successo health check
   */
  private handleSuccess(data: HealthResponse): void {
    this.updateState({
      status: 'online',
      lastSuccess: Date.now(),
      errorCount: 0,
      version: data.version,
      service: data.service,
    });
  }

  /**
   * Gestisce errore health check
   */
  private handleError(_error: { message: string }): void {
    const newErrorCount = this.state.errorCount + 1;
    const isOffline = newErrorCount >= this.config.retryCount;

    this.updateState({
      status: isOffline ? 'offline' : 'checking',
      errorCount: newErrorCount,
    });
  }

  /**
   * Aggiorna lo stato e notifica i callback
   */
  private updateState(updates: Partial<HealthMonitorState>): void {
    const prevStatus = this.state.status;
    this.state = { ...this.state, ...updates };

    // Notifica solo se lo stato è cambiato o è il primo update
    if (prevStatus !== this.state.status || updates.lastCheck === null) {
      this.notifyCallbacks();
    }
  }

  /**
   * Registra un callback per cambiamenti di stato
   */
  onStatusChange(callback: HealthStatusCallback): () => void {
    this.callbacks.push(callback);

    // Notifica immediatamente con lo stato corrente
    callback(this.state);

    return () => {
      this.callbacks = this.callbacks.filter(cb => cb !== callback);
    };
  }

  /**
   * Notifica tutti i callback
   */
  private notifyCallbacks(): void {
    const state = { ...this.state };
    this.callbacks.forEach(callback => {
      try {
        callback(state);
      } catch (error) {
        console.error('Error in health status callback:', error);
      }
    });
  }

  /**
   * Restituisce lo stato corrente
   */
  getCurrentState(): HealthMonitorState {
    return { ...this.state };
  }

  /**
   * Verifica se il server è online
   */
  isOnline(): boolean {
    return this.state.status === 'online';
  }

  /**
   * Verifica se il server è offline
   */
  isOffline(): boolean {
    return this.state.status === 'offline';
  }

  /**
   * Reimposta lo stato a 'checking' e azzera errori
   */
  reset(): void {
    this.updateState({
      status: 'checking',
      errorCount: 0,
      lastCheck: null,
      lastSuccess: null,
      version: undefined,
      service: undefined,
    });
  }

  /**
   * Ottiene il tempo dall'ultimo check riuscito
   */
  getTimeSinceLastSuccess(): number | null {
    if (!this.state.lastSuccess) return null;
    return Date.now() - this.state.lastSuccess;
  }

  /**
   * Formatta il tempo trascorso in formato leggibile
   */
  formatTimeSinceLastSuccess(): string {
    const ms = this.getTimeSinceLastSuccess();
    if (!ms) return 'Never';

    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return `${seconds}s ago`;
  }
}

/** Istanza globale del servizio health */
export const healthService = new HealthService();

// Avvia automaticamente il monitoraggio all'import
if (typeof window !== 'undefined') {
  // Avvia solo in browser, non in SSR
  setTimeout(() => {
    healthService.startMonitoring();
  }, 1000);
}