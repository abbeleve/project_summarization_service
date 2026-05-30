// import type { TranscriptPart, TranscriptSegment } from '@/types/transcript';

// export const extractSpeaker = (text: string): string => {
//   if (text.includes(':')) {
//     return text.split(':')[0].trim();
//   }
//   return 'UNKNOWN';
// };

// export const extractText = (text: string): string => {
//   if (text.includes(':')) {
//     return text.split(':').slice(1).join(':').trim();
//   }
//   return text;
// };

// export const countUniqueSpeakers = (parts: TranscriptPart[]): number => {
//   const speakers = new Set(parts.map(p => extractSpeaker(p.text)));
//   return speakers.size;
// };

// export const calculateTotalDuration = (parts: TranscriptPart[]): number => {
//   if (parts.length === 0) return 0;
//   const maxEnd = Math.max(...parts.map(p => p.end_time));
//   return maxEnd / 1000; // Convert ms to seconds
// };

// export const getSpeakerStats = (segments: TranscriptSegment[]) => {
//   const stats: Record<string, { duration: number; segments: number }> = {};
  
//   segments.forEach(seg => {
//     const speaker = seg.Speaker || 'UNKNOWN';
//     if (!stats[speaker]) {
//       stats[speaker] = { duration: 0, segments: 0 };
//     }
//     stats[speaker].duration += seg.stop - seg.start;
//     stats[speaker].segments += 1;
//   });
  
//   return Object.entries(stats).map(([speaker, data]) => ({
//     speaker,
//     ...data,
//     percentage: 0 // Will be calculated later
//   }));
// };