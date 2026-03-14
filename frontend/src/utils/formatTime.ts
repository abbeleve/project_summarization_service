export const formatTime = (seconds: number): string => {
  if (!seconds || isNaN(seconds)) return '0:00';
  
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const formatDuration = (seconds: number): string => {
  if (!seconds || isNaN(seconds)) return '0 сек';
  
  if (seconds < 60) {
    return `${Math.round(seconds)} сек`;
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${mins} мин ${secs} сек` : `${mins} мин`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor((seconds % 3600) % 60)
    if (secs > 0) {
      return `${hours} ч ${mins} мин ${secs} сек`;
    } else if (mins > 0) {
      return `${hours} ч ${mins} мин`;
    } else {
      return `${hours} ч`;
    }
  }
};