/**
 * Utility per la gestione del localStorage con TypeScript
 */

/** Opzioni per il salvataggio */
export interface StorageOptions<T> {
  defaultValue?: T;
  validator?: (value: any) => boolean;
  serializer?: (value: T) => string;
  deserializer?: (value: string) => T;
}

/**
 * Crea un gestore per un valore nel localStorage
 */
export function createStorage<T>(
  key: string,
  options: StorageOptions<T> = {}
) {
  const {
    defaultValue,
    validator = () => true,
    serializer = JSON.stringify,
    deserializer = JSON.parse,
  } = options;

  function get(): T | null {
    try {
      const item = localStorage.getItem(key);
      if (item === null) {
        return defaultValue || null;
      }

      const value = deserializer(item);
      if (!validator(value)) {
        remove();
        return defaultValue || null;
      }

      return value;
    } catch (error) {
      console.error(`Error reading from localStorage key "${key}":`, error);
      return defaultValue || null;
    }
  }

  function set(value: T): void {
    try {
      const serialized = serializer(value);
      localStorage.setItem(key, serialized);
    } catch (error) {
      console.error(`Error writing to localStorage key "${key}":`, error);
    }
  }

  function remove(): void {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error(`Error removing from localStorage key "${key}":`, error);
    }
  }

  function update(updater: (current: T | null) => T): void {
    const current = get();
    const updated = updater(current);
    set(updated);
  }

  return {
    get,
    set,
    remove,
    update,
    key,
  };
}

/**
 * Storage per il progetto corrente
 */
export const projectStorage = createStorage<string>('crick_project_root', {
  defaultValue: '',
});

/**
 * Storage per le impostazioni dell'utente
 */
export interface UserSettings {
  theme?: 'dark' | 'light';
  autoScroll?: boolean;
  showToolDetails?: boolean;
  notifications?: boolean;
}

export const userSettingsStorage = createStorage<UserSettings>('crick_user_settings', {
  defaultValue: {
    theme: 'dark',
    autoScroll: true,
    showToolDetails: true,
    notifications: true,
  },
});

/**
 * Storage per le impostazioni LLM
 */
export interface LLMSettings {
  provider: string;           // Es: "DeepSeek", "OpenAiLike", "OpenAIChat", "Gemini", "Nvidia", "Ollama", "OpenRouter", "Claude"
  model_id: string;           // Es: "deepseek-chat", "gpt-4o", "claude-3-5-sonnet"
  api_key: string;            // Chiave API
  temperature?: number;       // Default 0.2
}

export const llmSettingsStorage = createStorage<LLMSettings>('crick_llm_settings', {
  defaultValue: {
    provider: "DeepSeek",
    model_id: "deepseek-chat",
    api_key: "",
    temperature: 0.2,
  },
});

/**
 * Storage per lo stato UI (sidebar aperta/chiusa, etc.)
 */
export interface UIState {
  sidebarOpen: boolean;
  sessionPanelOpen: boolean;
  settingsPanelOpen: boolean;
}

export const uiStateStorage = createStorage<UIState>('crick_ui_state', {
  defaultValue: {
    sidebarOpen: true,
    sessionPanelOpen: false,
    settingsPanelOpen: false,
  },
});

/**
 * Pulisce tutto lo storage di Crick
 */
export function clearCrickStorage(): void {
  const keysToRemove: string[] = [];

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('crick_')) {
      keysToRemove.push(key);
    }
  }

  keysToRemove.forEach(key => localStorage.removeItem(key));
}

/**
 * Verifica se il localStorage è disponibile
 */
export function isLocalStorageAvailable(): boolean {
  try {
    const testKey = '__crick_test__';
    localStorage.setItem(testKey, 'test');
    localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

/**
 * Ottiene la dimensione totale dello storage usato da Crick (in byte)
 */
export function getCrickStorageSize(): number {
  let total = 0;

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('crick_')) {
      const value = localStorage.getItem(key) || '';
      total += key.length + value.length;
    }
  }

  // Approssimazione: ogni carattere = 2 byte (UTF-16)
  return total * 2;
}