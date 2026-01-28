import { Transcript } from "@/interfaces/transcript.interface";

interface ParsedTranscriptEntry {
  text: string;
  speaker: string;
  start_time: number;
  type?: string;
}

/**
 * Safely parse a transcript's transcription field
 * @param transcript The transcript to parse
 * @returns An array of parsed transcript entries or an empty array if parsing fails
 */
export const parseTranscription = (transcript: Transcript): ParsedTranscriptEntry[] => {
  try {
    if (!transcript) return [];
    
    const transcription = transcript.transcription;
    
    if (Array.isArray(transcription)) {
      return transcription.map(entry => ({
        speaker: entry.speaker || "Unknown",
        start_time: typeof entry.start_time === 'number' ? entry.start_time : 0,
        text: entry.text || "",
        type: entry.type || "message",
      }));
    }
    
    // if (typeof transcription === 'string') {
    //   try {
    //     const parsed = JSON.parse(transcription);
    //     if (Array.isArray(parsed)) {
    //       return parsed.map(entry => ({
    //         speaker: entry.speaker || "Unknown",
    //         start_time: typeof entry.start_time === 'number' ? entry.start_time : 0,
    //         text: entry.text || ""
    //       }));
    //     }
    //   } catch (e) {
    //     console.error("Error parsing JSON transcription:", e);
    //   }
    // }
    
    if (transcript.transcript && Array.isArray(transcript.transcript) && transcript.transcript.length > 0) {
      return transcript.transcript.map(entry => ({
        speaker: entry.speaker || "Unknown",
        start_time: typeof entry.start_time === 'number' ? entry.start_time : 0,
        text: entry.text || ""
      }));
    }
    
    return [];
  } catch (error) {
    return [];
  }
};

/**
 * Get a preview of the transcript text
 * @param transcript The transcript to get a preview for
 * @param maxLength Maximum length of the preview text
 * @returns A preview of the transcript text
 */
export const getTranscriptPreview = (
  transcript: Transcript, 
  maxLength: number = 100
): string | React.ReactNode => {
  if (!transcript) return "No transcription available";
  
  const parsedTranscript = parseTranscription(transcript);
  
  if (!parsedTranscript || parsedTranscript.length === 0) {
    return "No transcription available";
  }
  
  for (const entry of parsedTranscript) {
    // NOTE: handle file attachments
    if (entry.type === 'file') {
      const fileInfo = JSON.parse(entry.text);

      let content = '';
      if (fileInfo?.type.startsWith('image/')) {
        content += `<img src="${fileInfo?.url}" alt="${fileInfo?.name}" style="width: 30px; height: 30px;" />`;
      } else {
        content += `<a href="${fileInfo?.url}" target="_blank" rel="noopener noreferrer" style="color: #6b7280; text-decoration: underline;">${fileInfo?.name}</a>`;
      }

      return  `<div style="color: #6b7280; flex-direction: row; display: flex; align-items: center; gap: 4px;">File attached ${content}</div>`;
    }

    if (entry.text && entry.text.trim().length > 0) {
      return entry.text.slice(0, maxLength) + (entry.text.length > maxLength ? "..." : "");
    }
  }
  
  return "No transcription available";
};

/**
 * Group transcript entries by speaker
 * @param entries The parsed transcript entries
 * @returns An array of grouped transcript entries by speaker
 */
export const groupTranscriptByConversation = (entries: ParsedTranscriptEntry[]): {
  speaker: string;
  text: string;
  start_time: number;
}[] => {
  if (!entries || !Array.isArray(entries) || entries.length === 0) return [];
  
  const result = [];
  let currentSpeaker = '';
  let currentText = '';
  let currentStartTime = 0;
  
  for (const entry of entries) {
    if (!entry || !entry.speaker) continue;
    
    if (currentSpeaker === '') {
      currentSpeaker = entry.speaker;
      currentText = entry.text || '';
      currentStartTime = typeof entry.start_time === 'number' ? entry.start_time : 0;
    } else if (currentSpeaker === entry.speaker) {
      currentText += ' ' + (entry.text || '');
    } else {
      result.push({
        speaker: currentSpeaker,
        text: currentText,
        start_time: currentStartTime
      });
      
      currentSpeaker = entry.speaker;
      currentText = entry.text || '';
      currentStartTime = typeof entry.start_time === 'number' ? entry.start_time : 0;
    }
  }
  
  if (currentSpeaker !== '') {
    result.push({
      speaker: currentSpeaker,
      text: currentText,
      start_time: currentStartTime
    });
  }
  
  return result;
}; 