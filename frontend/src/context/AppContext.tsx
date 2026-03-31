import { createContext, type ReactNode, useState, useCallback } from 'react';
import type { ProcessingSettings, Transcript } from '@/types/transcript';
import { DEFAULT_SETTINGS } from '@/config/settings';

interface AppState {
  currentTranscript: Transcript | null;
  processingSettings: ProcessingSettings;
  isProcessing: boolean;
  error: string | null;
}

interface AppContextType extends AppState {
  setCurrentTranscript: (transcript: Transcript | null) => void;
  updateSettings: (settings: Partial<ProcessingSettings>) => void;
  resetSettings: () => void;
  setProcessing: (isProcessing: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AppState>({
    currentTranscript: null,
    processingSettings: DEFAULT_SETTINGS,
    isProcessing: false,
    error: null
  });

  const setCurrentTranscript = useCallback((transcript: Transcript | null) => {
    setState(prev => ({ ...prev, currentTranscript: transcript }));
  }, []);

  const updateSettings = useCallback((updates: Partial<ProcessingSettings>) => {
    setState(prev => ({
      ...prev,
      processingSettings: { ...prev.processingSettings, ...updates }
    }));
  }, []);

  const resetSettings = useCallback(() => {
    setState(prev => ({ ...prev, processingSettings: DEFAULT_SETTINGS }));
  }, []);

  const setProcessing = useCallback((isProcessing: boolean) => {
    setState(prev => ({ ...prev, isProcessing }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState(prev => ({ ...prev, error }));
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  return (
    <AppContext.Provider value={{
      ...state,
      setCurrentTranscript,
      updateSettings,
      resetSettings,
      setProcessing,
      setError,
      clearError
    }}>
      {children}
    </AppContext.Provider>
  );
};