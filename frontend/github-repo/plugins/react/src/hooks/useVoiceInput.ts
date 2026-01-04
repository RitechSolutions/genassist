import { useRef, useState, useEffect, useCallback } from 'react';

interface UseVoiceInputProps {
  baseUrl: string;
  apiKey: string;
  onTranscription: (text: string) => void;
  onError: (error: Error) => void;
}

interface UseVoiceInputReturn {
  isRecording: boolean;
  isLoading: boolean;
  isSessionActive: boolean;
  startSession: () => Promise<void>;
  stopSession: () => void;
  toggleRecording: () => void;
}

export const useVoiceInput = ({
  baseUrl,
  apiKey,
  onTranscription,
  onError,
}: UseVoiceInputProps): UseVoiceInputReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);
  
  const peerConnection = useRef<RTCPeerConnection | null>(null);
  const dataChannel = useRef<RTCDataChannel | null>(null);
  const audioElement = useRef<HTMLAudioElement | null>(null);

  const cleanup = useCallback(() => {
    if (dataChannel.current) {
      dataChannel.current.close();
      dataChannel.current = null;
    }

    if (peerConnection.current) {
      peerConnection.current.getSenders().forEach((sender) => {
        if (sender.track) {
          sender.track.stop();
        }
      });
      peerConnection.current.close();
      peerConnection.current = null;
    }

    if (audioElement.current) {
      audioElement.current.srcObject = null;
      audioElement.current = null;
    }

    setIsRecording(false);
    setIsSessionActive(false);
    setIsLoading(false);
  }, []);

  const handleDataChannelMessage = useCallback((event: MessageEvent) => {
    const data = JSON.parse(event.data);
    
    // Handle conversation item created events which may contain transcripts
    if (data.type === 'conversation.item.created' && data.item) {
      // Check if the item has content with transcript
      if (data.item.content && Array.isArray(data.item.content)) {
        for (const contentItem of data.item.content) {
          if (contentItem.type === 'input_audio' && contentItem.transcript) {
            onTranscription(contentItem.transcript);
            return;
          }
        }
      }
      
      // Check if the item itself has a transcript field
      if (data.item.transcript) {
        onTranscription(data.item.transcript);
        return;
      }
    }
    
    // Handle input audio transcription completed events
    if (data.type === 'conversation.item.input_audio_transcription.completed' && data.transcript) {
      onTranscription(data.transcript);
    }
    
    // Handle response audio transcript events
    if (data.type === 'response.audio_transcript.done' && data.transcript) {
      onTranscription(data.transcript);
    }
    
    // Check for any other events with transcript field
    if (data.transcript && !data.type.includes('error')) {
      onTranscription(data.transcript);
    }
  }, [onTranscription]);

  const startSession = useCallback(async () => {
    setIsLoading(true);
    try {
      // Get ephemeral API key from backend
      const tokenResponse = await fetch(`${baseUrl}api/voice/openai/session`, {
        headers: {
          'x-api-key': apiKey
        }
      });
      
      if (!tokenResponse.ok) {
        throw new Error('Failed to get ephemeral API key');
      }
      
      const ephemeralKey = await tokenResponse.json();

      // Create a peer connection
      const pc = new RTCPeerConnection();

      // Set up to play remote audio from the model
      audioElement.current = document.createElement("audio");
      audioElement.current.autoplay = true;
      pc.ontrack = (e) => {
        if (audioElement.current) {
          audioElement.current.srcObject = e.streams[0];
        }
      };

      // Add local audio track for microphone input
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      pc.addTrack(mediaStream.getTracks()[0]);

      // Set up data channel for sending and receiving events
      const dc = pc.createDataChannel("oai-events");
      dataChannel.current = dc;

      dc.onmessage = handleDataChannelMessage;
      
      dc.onopen = () => {
        setIsSessionActive(true);
        setIsLoading(false);
      };

      // Start the session using SDP
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const response = await fetch('https://api.openai.com/v1/realtime', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ephemeralKey}`,
          'Content-Type': 'application/sdp',
        },
        body: offer.sdp,
      });

      const answer: RTCSessionDescriptionInit = {
        type: 'answer',
        sdp: await response.text(),
      };

      await pc.setRemoteDescription(new RTCSessionDescription(answer));

      peerConnection.current = pc;
      setIsRecording(true);
    } catch (error) {
      onError(error as Error);
      cleanup();
    }
  }, [baseUrl, apiKey, handleDataChannelMessage, onError, cleanup]);

  const stopSession = useCallback(() => {
    cleanup();
  }, [cleanup]);

  const toggleRecording = useCallback(() => {
    if (isLoading) return;
    
    if (isRecording) {
      stopSession();
    } else {
      startSession();
    }
  }, [isLoading, isRecording, startSession, stopSession]);

  // Cleanup on component unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return {
    isRecording,
    isLoading,
    isSessionActive,
    startSession,
    stopSession,
    toggleRecording,
  };
}; 