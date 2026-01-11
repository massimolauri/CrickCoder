import { apiClient, buildProjectQuery, ApiClient } from './apiClient';
import type { Session, SessionsResponse, ApiResult } from '@/types/api.types';

/**
 * Servizio per la gestione delle sessioni
 */
export class SessionService {
  private storageKey = 'crick_session_data';

  /**
   * Recupera la lista delle sessioni per un progetto
   */
  async listSessions(projectPath: string): Promise<ApiResult<SessionsResponse>> {
    const query = buildProjectQuery(projectPath);
    return apiClient.get<SessionsResponse>('/sessions', query);
  }

  /**
   * Salva la sessione corrente nel localStorage
   */
  saveCurrentSession(projectPath: string, sessionId: string): void {
    const data = this.getStoredSessions();
    const cleanPath = ApiClient.cleanProjectPath(projectPath);

    data[cleanPath] = {
      sessionId,
      timestamp: Date.now(),
    };

    localStorage.setItem(this.storageKey, JSON.stringify(data));
  }

  /**
   * Recupera la sessione corrente per un progetto
   */
  getCurrentSession(projectPath: string): string | null {
    const data = this.getStoredSessions();
    const cleanPath = ApiClient.cleanProjectPath(projectPath);

    const sessionData = data[cleanPath];
    if (!sessionData) {
      return null;
    }

    // Opzionale: puoi aggiungere validazione della scadenza qui
    // const isExpired = Date.now() - sessionData.timestamp > 24 * 60 * 60 * 1000; // 24h
    // if (isExpired) {
    //   this.clearSession(projectPath);
    //   return null;
    // }

    return sessionData.sessionId;
  }

  /**
   * Cancella la sessione memorizzata per un progetto
   */
  clearSession(projectPath: string): void {
    const data = this.getStoredSessions();
    const cleanPath = ApiClient.cleanProjectPath(projectPath);

    delete data[cleanPath];
    localStorage.setItem(this.storageKey, JSON.stringify(data));
  }

  /**
   * Cancella tutte le sessioni memorizzate
   */
  clearAllSessions(): void {
    localStorage.removeItem(this.storageKey);
  }

  /**
   * Recupera i dati delle sessioni dal localStorage
   */
  private getStoredSessions(): Record<string, { sessionId: string; timestamp: number }> {
    try {
      const data = localStorage.getItem(this.storageKey);
      return data ? JSON.parse(data) : {};
    } catch {
      return {};
    }
  }

  /**
   * Formatta una data per visualizzazione
   */
  formatSessionDate(dateString: string): string {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('it-IT', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  }

  /**
   * Filtra sessioni per data (più recenti prima)
   */
  sortSessionsByDate(sessions: Session[]): Session[] {
    return [...sessions].sort((a, b) => {
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
  }

  /**
   * Raggruppa sessioni per data (oggi, ieri, questa settimana, etc.)
   */
  groupSessionsByDate(sessions: Session[]): Record<string, Session[]> {
    const groups: Record<string, Session[]> = {};
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    sessions.forEach(session => {
      const sessionDate = new Date(session.updated_at);
      let group = 'Older';

      if (sessionDate >= today) {
        group = 'Today';
      } else if (sessionDate >= yesterday) {
        group = 'Yesterday';
      } else if (sessionDate >= weekAgo) {
        group = 'This week';
      }

      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push(session);
    });

    return groups;
  }

  /**
   * Genera un ID sessione locale (usato quando il backend non ne fornisce uno)
   */
  generateLocalSessionId(): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 9);
    return `local_${timestamp}_${random}`;
  }

  /**
   * Cancella una sessione dal backend
   */
  async deleteSession(sessionId: string, projectPath?: string): Promise<ApiResult<{ success: boolean; message: string }>> {
    try {
      // Endpoint base
      let endpoint = `/sessions/${encodeURIComponent(sessionId)}`;

      // Aggiungi project_path come query param se fornito
      if (projectPath) {
        const query = buildProjectQuery(projectPath);
        endpoint = `${endpoint}?${new URLSearchParams(query).toString()}`;
      }

      // Usa il metodo request direttamente poiché apiClient potrebbe non avere delete()
      return await apiClient.request<{ success: boolean; message: string }>(
        'DELETE',
        endpoint,
        undefined,
        { headers: {} }
      );
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : 'Failed to delete session',
        },
      };
    }
  }

  /**
   * Carica la cronologia di una sessione dal backend
   */
  async loadSessionHistory(sessionId: string, projectPath?: string): Promise<ApiResult<{ messages: any[] }>> {
    try {
      // Endpoint base
      let endpoint = `/sessions/${encodeURIComponent(sessionId)}/history`;

      // Aggiungi project_path come query param se fornito
      if (projectPath) {
        const query = buildProjectQuery(projectPath);
        endpoint = `${endpoint}?${new URLSearchParams(query).toString()}`;
      }

      return await apiClient.request<{ messages: any[] }>(
        'GET',
        endpoint,
        undefined,
        { headers: {} }
      );
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : 'Failed to load session history',
        },
      };
    }
  }
}

/** Istanza globale del servizio sessioni */
export const sessionService = new SessionService();