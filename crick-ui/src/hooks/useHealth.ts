import { useState, useEffect, useCallback } from 'react';
import { healthService } from '@/services/healthService';
import type { HealthMonitorState } from '@/types/api.types';

/** Opzioni per useHealth */
export interface UseHealthOptions {
  autoStart?: boolean;
  onStatusChange?: (state: HealthMonitorState) => void;
  onOnline?: () => void;
  onOffline?: () => void;
}

/**
 * Hook per il monitoraggio dello stato del server
 */
export function useHealth(options: UseHealthOptions = {}) {
  const {
    autoStart = true,
    onStatusChange,
    onOnline,
    onOffline,
  } = options;

  const [state, setState] = useState<HealthMonitorState>(
    healthService.getCurrentState()
  );

  /**
   * Esegue un check manuale
   */
  const checkHealth = useCallback(async () => {
    return healthService.checkHealth();
  }, []);

  /**
   * Avvia il monitoraggio periodico
   */
  const startMonitoring = useCallback(() => {
    healthService.startMonitoring();
  }, []);

  /**
   * Ferma il monitoraggio periodico
   */
  const stopMonitoring = useCallback(() => {
    healthService.stopMonitoring();
  }, []);

  /**
   * Reimposta lo stato
   */
  const reset = useCallback(() => {
    healthService.reset();
  }, []);

  // Sottoscrizione ai cambiamenti di stato
  useEffect(() => {
    const unsubscribe = healthService.onStatusChange((newState) => {
      setState(newState);
      onStatusChange?.(newState);

      // Trigger eventi specifici
      if (newState.status === 'online') {
        onOnline?.();
      } else if (newState.status === 'offline') {
        onOffline?.();
      }
    });

    // Avvia monitoraggio se richiesto
    if (autoStart) {
      startMonitoring();
    }

    return () => {
      unsubscribe();
      if (autoStart) {
        stopMonitoring();
      }
    };
  }, [autoStart, onStatusChange, onOnline, onOffline, startMonitoring, stopMonitoring]);

  return {
    // Stato
    status: state.status,
    lastCheck: state.lastCheck,
    lastSuccess: state.lastSuccess,
    errorCount: state.errorCount,
    version: state.version,
    service: state.service,

    // Azioni
    checkHealth,
    startMonitoring,
    stopMonitoring,
    reset,

    // Helper
    isOnline: state.status === 'online',
    isOffline: state.status === 'offline',
    isChecking: state.status === 'checking',
    timeSinceLastSuccess: healthService.getTimeSinceLastSuccess(),
    formattedTimeSinceLastSuccess: healthService.formatTimeSinceLastSuccess(),

    // Stato completo
    state,
  };
}

/**
 * Hook per un indicatore di stato semplice (icona + tooltip)
 */
export function useHealthIndicator(options?: UseHealthOptions) {
  const health = useHealth(options);

  const getIndicatorProps = useCallback(() => {
    switch (health.status) {
      case 'online':
        return {
          color: 'text-emerald-500',
          bgColor: 'bg-emerald-500/20',
          icon: '●',
          tooltip: `Online - ${health.formattedTimeSinceLastSuccess}`,
          pulse: false,
        };

      case 'offline':
        return {
          color: 'text-red-500',
          bgColor: 'bg-red-500/20',
          icon: '●',
          tooltip: `Offline - ${health.errorCount} errors`,
          pulse: false,
        };

      case 'checking':
        return {
          color: 'text-amber-500',
          bgColor: 'bg-amber-500/20',
          icon: '⟳',
          tooltip: 'Checking server status...',
          pulse: true,
        };

      default:
        return {
          color: 'text-slate-500',
          bgColor: 'bg-slate-500/20',
          icon: '?',
          tooltip: 'Unknown status',
          pulse: false,
        };
    }
  }, [health.status, health.formattedTimeSinceLastSuccess, health.errorCount]);

  const getStatusText = useCallback(() => {
    switch (health.status) {
      case 'online': return 'Server online';
      case 'offline': return 'Server offline';
      case 'checking': return 'Checking...';
      default: return 'Unknown';
    }
  }, [health.status]);

  return {
    ...health,
    indicatorProps: getIndicatorProps(),
    statusText: getStatusText(),
  };
}

/**
 * Hook per il banner di stato (mostrato quando il server è offline)
 */
export function useHealthBanner(
  options: UseHealthOptions & {
    showWhenOffline?: boolean;
    showWhenChecking?: boolean;
    autoHideDelay?: number; // ms
  } = {}
) {
  const {
    showWhenOffline = true,
    showWhenChecking = false,
    autoHideDelay,
    ...healthOptions
  } = options;

  const health = useHealth(healthOptions);
  const [visible, setVisible] = useState(false);

  // Mostra/nascondi banner in base allo stato
  useEffect(() => {
    const shouldShow =
      (showWhenOffline && health.isOffline) ||
      (showWhenChecking && health.isChecking);

    setVisible(shouldShow);

    // Auto-hide per stati temporanei
    if (autoHideDelay && health.isChecking) {
      const timer = setTimeout(() => {
        setVisible(false);
      }, autoHideDelay);

      return () => clearTimeout(timer);
    }
  }, [health.isOffline, health.isChecking, showWhenOffline, showWhenChecking, autoHideDelay]);

  const dismiss = useCallback(() => {
    setVisible(false);
  }, []);

  const show = useCallback(() => {
    setVisible(true);
  }, []);

  const bannerProps = useCallback(() => {
    if (health.isOffline) {
      return {
        title: 'Server offline',
        message: 'Unable to connect to the Crick server. Please check your connection.',
        severity: 'error' as const,
        color: 'bg-red-500/10 border-red-500/30 text-red-400',
        icon: '⚠',
        action: {
          label: 'Retry',
          onClick: health.checkHealth,
        },
      };
    }

    if (health.isChecking) {
      return {
        title: 'Checking server',
        message: 'Verifying server connection...',
        severity: 'warning' as const,
        color: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
        icon: '⟳',
        action: null,
      };
    }

    return null;
  }, [health.isOffline, health.isChecking, health.checkHealth]);

  return {
    ...health,
    visible,
    dismiss,
    show,
    bannerProps: bannerProps(),
  };
}