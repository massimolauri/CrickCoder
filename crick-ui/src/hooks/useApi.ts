import { useState, useCallback, useRef } from 'react';
import type { ApiResult, ApiError } from '@/types/api.types';

/** Stato della richiesta API */
export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

/** Opzioni per useApi */
export interface UseApiOptions<T> {
  initialData?: T | null;
  onSuccess?: (data: T) => void;
  onError?: (error: ApiError) => void;
  immediate?: boolean;
}

/**
 * Hook generico per gestire chiamate API
 */
export function useApi<T>(
  apiCall: () => Promise<ApiResult<T>>,
  options: UseApiOptions<T> = {}
) {
  const {
    initialData = null,
    onSuccess,
    onError,
    immediate = false,
  } = options;

  const [state, setState] = useState<ApiState<T>>({
    data: initialData,
    loading: immediate,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const execute = useCallback(async (): Promise<ApiResult<T>> => {
    // Cancella richiesta precedente
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const result = await apiCall();

      if (result.success) {
        setState({
          data: result.data,
          loading: false,
          error: null,
        });
        onSuccess?.(result.data);
      } else {
        setState({
          data: null,
          loading: false,
          error: result.error,
        });
        onError?.(result.error);
      }

      return result;

    } catch (error) {
      const apiError: ApiError = {
        message: error instanceof Error ? error.message : 'Unknown error',
      };

      setState({
        data: null,
        loading: false,
        error: apiError,
      });

      onError?.(apiError);

      return {
        success: false,
        error: apiError,
      };
    } finally {
      abortControllerRef.current = null;
    }
  }, [apiCall, onSuccess, onError]);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setState({
      data: initialData,
      loading: false,
      error: null,
    });
  }, [initialData]);

  // Esegue immediatamente se richiesto
  const executeRef = useRef(execute);
  executeRef.current = execute;

  // useEffect per immediate execution
  // Nota: implementato nel componente che usa l'hook

  return {
    ...state,
    execute,
    reset,
    isSuccess: state.data !== null && !state.error,
    isError: state.error !== null,
  };
}

/**
 * Hook per chiamate API con parametri
 */
export function useApiWithParams<P, T>(
  apiCall: (params: P) => Promise<ApiResult<T>>,
  options: UseApiOptions<T> = {}
) {
  const [params, setParams] = useState<P | null>(null);

  const apiCallWrapper = useCallback(async (): Promise<ApiResult<T>> => {
    if (!params) {
      return {
        success: false,
        error: { message: 'No parameters provided' },
      };
    }
    return apiCall(params);
  }, [apiCall, params]);

  const { execute, ...apiState } = useApi(apiCallWrapper, {
    ...options,
    immediate: false,
  });

  const executeWithParams = useCallback(async (newParams: P) => {
    setParams(newParams);
    // Piccolo delay per garantire che params sia aggiornato
    await Promise.resolve();
    return execute();
  }, [execute]);

  return {
    ...apiState,
    execute: executeWithParams,
    params,
  };
}

/**
 * Hook per polling API
 */
export function useApiPolling<T>(
  apiCall: () => Promise<ApiResult<T>>,
  interval: number = 30000,
  options: UseApiOptions<T> = {}
) {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const apiState = useApi(apiCall, {
    ...options,
    immediate: true,
  });

  const startPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Esegui immediatamente
    apiState.execute();

    // Poi a intervalli regolari
    intervalRef.current = setInterval(() => {
      apiState.execute();
    }, interval);
  }, [apiState.execute, interval]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Pulisci interval al unmount
  // useEffect(() => {
  //   return () => {
  //     stopPolling();
  //   };
  // }, [stopPolling]);

  return {
    ...apiState,
    startPolling,
    stopPolling,
    isPolling: intervalRef.current !== null,
  };
}