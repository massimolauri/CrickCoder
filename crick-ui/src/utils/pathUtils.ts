/**
 * Utility per la gestione dei path di progetto
 */

/**
 * Pulisce un path progetto rimuovendo virgolette e spazi extra
 */
export function cleanProjectPath(projectPath: string): string {
  return projectPath.trim().replace(/^["']|["']$/g, '');
}

/**
 * Verifica se un path è assoluto (Windows o Unix)
 */
export function isAbsolutePath(path: string): boolean {
  const cleaned = cleanProjectPath(path);

  // Windows: C:\ o \\server\
  if (/^[a-zA-Z]:\\/.test(cleaned) || /^\\\\/.test(cleaned)) {
    return true;
  }

  // Unix: /home o ~/
  if (cleaned.startsWith('/') || cleaned.startsWith('~/')) {
    return true;
  }

  return false;
}

/**
 * Estrae il nome del progetto dal path
 */
export function getProjectName(projectPath: string): string {
  const cleaned = cleanProjectPath(projectPath);

  if (!cleaned) return 'No Project';

  // Prendi l'ultima parte del path
  const parts = cleaned.split(/[\\/]/).filter(part => part.trim());
  return parts[parts.length - 1] || 'Unknown Project';
}

/**
 * Tronca un path per visualizzazione (aggiunge ... se troppo lungo)
 */
export function truncatePath(
  path: string,
  maxLength: number = 50,
  ellipsis: string = '...'
): string {
  const cleaned = cleanProjectPath(path);

  if (cleaned.length <= maxLength) {
    return cleaned;
  }

  const keepLength = Math.floor((maxLength - ellipsis.length) / 2);
  const start = cleaned.substring(0, keepLength);
  const end = cleaned.substring(cleaned.length - keepLength);

  return `${start}${ellipsis}${end}`;
}

/**
 * Normalizza i separatori di path (converte / in \ su Windows se necessario)
 */
export function normalizePathSeparators(path: string): string {
  const cleaned = cleanProjectPath(path);

  // Su Windows, possiamo convertire / in \ per consistenza
  if (process.platform === 'win32') {
    return cleaned.replace(/\//g, '\\');
  }

  // Su Unix, converti \ in /
  return cleaned.replace(/\\/g, '/');
}

/**
 * Verifica se due path puntano alla stessa directory (ignorando separatori e case su Windows)
 */
export function arePathsEqual(path1: string, path2: string): boolean {
  const clean1 = normalizePathSeparators(cleanProjectPath(path1));
  const clean2 = normalizePathSeparators(cleanProjectPath(path2));

  if (process.platform === 'win32') {
    return clean1.toLowerCase() === clean2.toLowerCase();
  }

  return clean1 === clean2;
}

/**
 * Estrae la directory padre da un path
 */
export function getParentDirectory(path: string): string | null {
  const cleaned = cleanProjectPath(path);
  const normalized = normalizePathSeparators(cleaned);
  const parts = normalized.split(/[\\/]/).filter(part => part.trim());

  if (parts.length <= 1) {
    return null;
  }

  parts.pop(); // Rimuovi l'ultima parte (nome file/dir)
  return parts.join(process.platform === 'win32' ? '\\' : '/');
}

/**
 * Valida che un path sembri valido (controlli base)
 */
export function isValidProjectPath(path: string): {
  valid: boolean;
  reason?: string;
} {
  const cleaned = cleanProjectPath(path);

  if (!cleaned) {
    return { valid: false, reason: 'Path is empty' };
  }

  if (cleaned.length > 260) {
    return { valid: false, reason: 'Path too long (max 260 characters)' };
  }

  // Controlla caratteri non validi (controllo base)
  const invalidChars = /[<>:"|?*]/;
  if (invalidChars.test(cleaned)) {
    return { valid: false, reason: 'Path contains invalid characters' };
  }

  return { valid: true };
}

/**
 * Formatta un path per visualizzazione UI
 */
export function formatPathForDisplay(
  path: string,
  options: {
    truncate?: number;
    showProjectName?: boolean;
  } = {}
): string {
  const { truncate = 50, showProjectName = false } = options;
  const cleaned = cleanProjectPath(path);

  if (showProjectName) {
    const projectName = getProjectName(cleaned);
    if (truncate && cleaned.length > truncate) {
      return `${projectName} (${truncatePath(cleaned, truncate)})`;
    }
    return projectName;
  }

  return truncatePath(cleaned, truncate);
}

/**
 * Crea un oggetto con informazioni sul path
 */
export function analyzeProjectPath(projectPath: string) {
  const cleaned = cleanProjectPath(projectPath);

  return {
    original: projectPath,
    cleaned,
    isAbsolute: isAbsolutePath(cleaned),
    projectName: getProjectName(cleaned),
    parentDirectory: getParentDirectory(cleaned),
    isValid: isValidProjectPath(cleaned),
    display: formatPathForDisplay(cleaned),
    displayWithName: formatPathForDisplay(cleaned, { showProjectName: true }),
  };
}