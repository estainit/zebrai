import { v4 as uuidv4 } from 'uuid';

// WebSocket configuration
const BACKEND_WS_URL = 'wss://cryptafe.io/ws';
const TIMESLICE_MS = 2000; // Send chunks every 2 seconds

// Detect iOS device
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
console.log('Is iOS device:', isIOS);

// Get supported MIME type
const getSupportedMimeType = () => {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
    'audio/wav'
  ];
  
  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      console.log('Using MIME type:', type);
      return type;
    }
  }
  
  // If no supported type is found, return null to use browser default
  console.warn('No supported MIME type found, using browser default');
  return null;
};

// Get iOS-specific audio settings
const getIOSAudioSettings = () => {
  return {
    mimeType: 'audio/mp4',
    audioBitsPerSecond: 128000
  };
};

export const startRecording = async ({ 
    isLoggedIn, 
    authToken, 
    webSocketRef, 
    setIsRecording, 
    setRecordingDuration, 
    setRecordingStartTime,
    setError,
    setTranscript,
    audioChunksRef,
    mediaRecorderRef,
    audioStreamRef,
    handleSessionExpired
}) => {
    if (!isLoggedIn) return;
    
    // Generate a new session ID for each recording
    const newSessionId = uuidv4();
    
    // Reset states
    if (setError) setError('');
    if (setTranscript) setTranscript(''); // Clear previous transcript
    if (audioChunksRef) audioChunksRef.current = []; // Clear chunks
    if (setRecordingDuration) setRecordingDuration(0);
    if (setRecordingStartTime) setRecordingStartTime(Date.now());

    try {
        // 1. Get audio stream
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (audioStreamRef) audioStreamRef.current = stream;

        // 2. Create MediaRecorder with supported MIME type
        let recorderOptions = {};
        
        if (isIOS) {
            // Use iOS-specific settings
            recorderOptions = getIOSAudioSettings();
            console.log('Using iOS-specific recorder options:', recorderOptions);
        } else {
            // Use detected MIME type for non-iOS devices
            const mimeType = getSupportedMimeType();
            if (mimeType) {
                recorderOptions = { mimeType };
            }
        }
        
        const recorder = new MediaRecorder(stream, recorderOptions);
        if (mediaRecorderRef) mediaRecorderRef.current = recorder;

        // 3. Connect WebSocket
        if (webSocketRef?.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
        }

        // Detect client type
        const userAgent = navigator.userAgent.toLowerCase();
        let clientType = 'unknown';
        
        if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
            clientType = 'ios';
        } else if (userAgent.includes('macintosh')) {
            clientType = 'mac';
        } else if (userAgent.includes('windows')) {
            clientType = 'windows';
        } else if (userAgent.includes('linux')) {
            clientType = 'linux';
        } else if (userAgent.includes('android')) {
            clientType = 'android';
        }

        const ws = new WebSocket(`${BACKEND_WS_URL}/${newSessionId}?client_type=${clientType}`);
        if (webSocketRef) webSocketRef.current = ws;
        
        ws.onopen = () => {
            console.log('WebSocket connected');
            // Send token in the connection
            ws.send(JSON.stringify({ type: 'auth', token: authToken }));
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log('Received WebSocket message:', message);
                
                if (message.type === 'transcript' && message.text && setTranscript) {
                    console.log('Received transcript:', message.text);
                    // Update transcript with proper spacing
                    setTranscript((prev) => {
                        // If this is the first transcript, don't add a space
                        if (!prev) return message.text;
                        // Otherwise, add a space only if the previous text doesn't end with punctuation
                        const lastChar = prev.trim().slice(-1);
                        const needsSpace = !['.', '!', '?', ','].includes(lastChar);
                        return prev + (needsSpace ? ' ' : '') + message.text;
                    });
                } else if (message.type === 'error' && setError) {
                    console.error('Received error from backend:', message.message);
                    if (message.message.includes('Session expired') || message.message.includes('Invalid token')) {
                        if (handleSessionExpired) handleSessionExpired();
                    } else {
                        setError(`Backend Error: ${message.message}`);
                    }
                }
            } catch (e) {
                console.error('Failed to parse message:', event.data, e);
            }
        };

        ws.onerror = (event) => {
            console.error('WebSocket Error:', event);
            if (setError) setError('WebSocket connection error. Please check your credentials.');
        };

        ws.onclose = (event) => {
            console.log('WebSocket Disconnected:', event.reason);
            if (event.code === 4001 || event.code === 4002) {
                if (setError) setError('Authentication failed. Please log in again.');
                if (handleSessionExpired) handleSessionExpired();
            }
        };

        // 4. Handle data chunks
        recorder.ondataavailable = (event) => {
            if (event.data.size > 0 && webSocketRef?.current?.readyState === WebSocket.OPEN) {
                console.log(`Sending audio chunk: ${event.data.size} bytes`);
                if (audioChunksRef) audioChunksRef.current.push(event.data); // Store locally if needed
                webSocketRef.current.send(event.data); // Send blob directly
            } else if (webSocketRef?.current?.readyState !== WebSocket.OPEN) {
                console.warn('WebSocket not open. Cannot send audio chunk.');
                // Don't stop recording here, just log the warning
            }
        };

        // 5. Handle recording stop
        recorder.onstop = () => {
            if (webSocketRef?.current) {
                webSocketRef.current.close();
                webSocketRef.current = null;
            }
            if (audioStreamRef?.current) {
                audioStreamRef.current.getTracks().forEach(track => track.stop());
                audioStreamRef.current = null;
            }
            if (setIsRecording) setIsRecording(false);
            if (setRecordingDuration) setRecordingDuration(0);
        };

        // Start recording
        recorder.start(TIMESLICE_MS);
        if (setIsRecording) setIsRecording(true);

        return recorder;
    } catch (err) {
        console.error('Error starting recording:', err);
        if (webSocketRef?.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
        }
        if (setIsRecording) setIsRecording(false);
        if (setRecordingDuration) setRecordingDuration(0);
        if (setError) setError(err.message);
        return null;
    }
};

export const stopRecording = ({ 
    mediaRecorderRef, 
    webSocketRef, 
    audioStreamRef, 
    setIsRecording, 
    setRecordingDuration, 
    durationIntervalRef 
}) => {
    console.log('Stopping recording...');
    
    // Stop the media recorder if it exists and is recording
    if (mediaRecorderRef?.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
    }
    
    // Close WebSocket connection after a short delay to ensure all data is sent
    setTimeout(() => {
        // Close WebSocket if it exists
        if (webSocketRef?.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
        }
        
        // Stop audio tracks if they exist
        if (audioStreamRef?.current) {
            audioStreamRef.current.getTracks().forEach(track => track.stop());
            audioStreamRef.current = null;
        }
        
        // Clear interval if it exists
        if (durationIntervalRef?.current) {
            clearInterval(durationIntervalRef.current);
            durationIntervalRef.current = null;
        }
        
        // Reset recording state
        if (setIsRecording) setIsRecording(false);
        if (setRecordingDuration) setRecordingDuration(0);
        
        // Automatically refresh the transcription list after a short delay
        // to ensure the new recording is saved in the database
        setTimeout(() => {
            const transcriptionList = document.querySelector('.transcription-list');
            if (transcriptionList) {
                const refreshButton = transcriptionList.querySelector('.refresh-button');
                if (refreshButton) {
                    refreshButton.click();
                }
            }
        }, 2000); // Wait 2 seconds to ensure the recording is saved
    }, 1000);
}; 