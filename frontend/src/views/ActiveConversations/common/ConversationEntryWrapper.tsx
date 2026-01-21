import { TranscriptEntry } from "@/interfaces/transcript.interface";


/**
 * FilePreview component
 * @param fileData - The file data
 * @returns The file preview component
 */
function FilePreview({ fileData }: { fileData: { url: string, name: string } }) {
  return <div className="flex flex-col items-start gap-2 cursor-pointer" onClick={() => window.open(fileData.url, '_blank')}>
    <img className="w-20 h-12 object-cover" src={fileData.url} alt="Image" loading="lazy" />
    <span className="text-xs text-muted-foreground">{fileData.name}</span>
  </div>;
}

export function ConversationEntryWrapper({ entry }: { entry: TranscriptEntry }) {
  try {
    if (entry.type === "image_url") {
      const fileData = JSON.parse(entry.text);
      return <FilePreview fileData={fileData} />;
    } else {
      return <div>{entry.text}</div>;
    }
  } catch (error) {
    console.error("Error parsing entry text:", error);
    return <></>;
  }
}
