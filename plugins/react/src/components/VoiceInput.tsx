import React, { useEffect, useRef, useState } from 'react';

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  onError: (error: Error) => void;
  baseUrl: string;
  apiKey: string;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    fontFamily?: string;
  };
}

export const VoiceInput: React.FC<VoiceInputProps> = ({
  onTranscription,
  onError,
  baseUrl,
  apiKey,
  theme
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);
  const peerConnection = useRef<RTCPeerConnection | null>(null);
  const dataChannel = useRef<RTCDataChannel | null>(null);
  const audioElement = useRef<HTMLAudioElement | null>(null);

  const startSession = async () => {
    try {
      // Get ephemeral API key from backend
      const tokenResponse = await fetch(`${baseUrl}/api/voice/openai/session`, {
        headers: {
          'x-api-key': apiKey
        }
      });
      
      if (!tokenResponse.ok) {
        throw new Error('Failed to get ephemeral API key');
      }
      
      const ephemeralKey  = await tokenResponse.json();

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

      // Set up data channel event listeners
      dc.onmessage = (event) => {
        console.log('Received message:', event.data);
        const data = JSON.parse(event.data);
        if (data.type === 'conversation.item.input_audio_transcription.completed' && data.transcript) {
          onTranscription(data.transcript);
        }
      };
      
      dc.onopen = () => {
        console.log('Data channel opened');
        setIsSessionActive(true);

        const updateSession = {
          type: "session.update",
          event_id: "message_004",
          session: {
            input_audio_transcription: {
              model: "whisper-1"
            }
          },
        };

        //dc.send(JSON.stringify(updateSession));
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
      console.error('Error session:', error);
      onError(error as Error);
      stopSession();
    }
  };

  const stopSession = () => {
    console.log('Stopping session');  
    if (dataChannel.current) {
      dataChannel.current.close();
    }

    if (peerConnection.current) {
      peerConnection.current.getSenders().forEach((sender) => {
        if (sender.track) {
          sender.track.stop();
        }
      });
      peerConnection.current.close();
    }

    if (audioElement.current) {
      audioElement.current.srcObject = null;
    }

    setIsRecording(false);
    setIsSessionActive(false);
    peerConnection.current = null;
    dataChannel.current = null;
  };

  const buttonStyle: React.CSSProperties = {
    backgroundColor: isRecording ? theme?.primaryColor || '#007bff' : '#f0f0f0',
    color: isRecording ? '#ffffff' : '#333333',
    border: 'none',
    borderRadius: '50%',
    width: '40px',
    height: '40px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    transition: 'all 0.3s ease',
  };

  return (
    <button
      style={buttonStyle}
      onClick={() => (isRecording ? stopSession() : startSession())}
      title={isRecording ? 'Stop Recording' : 'Start Recording'}
    >
      {isRecording ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="6" y="6" width="12" height="12" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="6" />
        </svg>
      )}
    </button>
  );
}; 