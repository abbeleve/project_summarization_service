// import { useState, useCallback } from 'react';
// import { transcriptsApi } from '@/api/transcripts';

// export const useAudioProcessing = () => {
//   const [isProcessing, setIsProcessing] = useState(false);
//   const [progress, setProgress] = useState(0);
//   const [error, setError] = useState<string | null>(null);

//   const applyNoiseSuppression = useCallback(async (file: File): Promise<Blob | null> => {
//     setIsProcessing(true);
//     setProgress(0);
//     setError(null);
    
//     try {
//       // Имитация прогресса (так как API не поддерживает streaming)
//       const interval = setInterval(() => {
//         setProgress(prev => Math.min(prev + 10, 90));
//       }, 500);
      
//       const result = await transcriptsApi.applyNoiseSuppression(file);
      
//       clearInterval(interval);
//       setProgress(100);
      
//       return result;
//     } catch (err) {
//       setError(err instanceof Error ? err.message : 'Ошибка обработки');
//       return null;
//     } finally {
//       setIsProcessing(false);
//       setTimeout(() => setProgress(0), 2000);
//     }
//   }, []);

//   const reset = useCallback(() => {
//     setIsProcessing(false);
//     setProgress(0);
//     setError(null);
//   }, []);

//   return {
//     isProcessing,
//     progress,
//     error,
//     applyNoiseSuppression,
//     reset
//   };
// };