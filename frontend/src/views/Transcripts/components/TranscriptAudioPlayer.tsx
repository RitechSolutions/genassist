type TranscriptAudioPlayerProps = {
  isLoading: boolean;
  audioSrc?: string;
  className?: string;
};

export function TranscriptAudioPlayer({
  isLoading,
  audioSrc,
  className = "",
}: TranscriptAudioPlayerProps) {
  return (
    <div className={`bg-primary/5 p-4 rounded-lg ${className}`}>
      {isLoading ? (
        <div className="animate-pulse">
          <div className="h-14 bg-gray-300 rounded-md w-full" />
        </div>
      ) : audioSrc ? (
        <audio
          controls
          className="w-full [&::-webkit-media-controls-panel]:bg-white [&::-webkit-media-controls-panel]:text-black"
        >
          <source src={audioSrc} type="audio/mpeg" />
          Your browser does not support the audio element.
        </audio>
      ) : (
        <div className="text-center text-sm text-muted-foreground py-2">
          No audio available for this call
        </div>
      )}
    </div>
  );
}