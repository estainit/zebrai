import { v4 as uuidv4 } from 'uuid';
import { getClientType, isIOS, getSupportedMimeType, getIOSAudioSettings } from '../utils/utils';

// WebSocket configuration
const BACKEND_WS_URL = 'wss://cryptafe.io/ws';
const TIMESLICE_MS = 2000; // Send chunks every 2 seconds

// Detect iOS device
const isIOSDevice = isIOS();
console.log('Is iOS device:', isIOSDevice);


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
    handleSessionExpired,
    durationIntervalRef
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
        
        if (isIOS()) {
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

        // Add a flag to track if recording is active
        let isRecordingActive = true;

        // Start duration counter
        if (durationIntervalRef) {
            // Clear any existing interval
            if (durationIntervalRef.current) {
                clearInterval(durationIntervalRef.current);
            }
            // Set up new interval
            durationIntervalRef.current = setInterval(() => {
                if (setRecordingDuration && isRecordingActive) {
                    setRecordingDuration(prev => prev + 1);
                }
            }, 1000);
        }

        // 3. Connect WebSocket
        if (webSocketRef?.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
        }

        // Get client type
        const clientType = getClientType();
        console.log('Detected client type:', clientType);

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
            // Only send data if recording is still active
            if (isRecordingActive && event.data.size > 0 && webSocketRef?.current?.readyState === WebSocket.OPEN) {
                console.log(`Sending audio chunk: ${event.data.size} bytes`);
                if (audioChunksRef) audioChunksRef.current.push(event.data); // Store locally if needed
                webSocketRef.current.send(event.data); // Send blob directly
            }
        };

        // 5. Handle recording stop
        recorder.onstop = () => {
            isRecordingActive = false; // Set flag to false when recording stops
            // Clear the duration interval
            if (durationIntervalRef?.current) {
                clearInterval(durationIntervalRef.current);
                durationIntervalRef.current = null;
            }
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
        // Clear interval if it exists
        if (durationIntervalRef?.current) {
            clearInterval(durationIntervalRef.current);
            durationIntervalRef.current = null;
        }
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
    
    // First, stop the media recorder if it exists and is recording
    if (mediaRecorderRef?.current && mediaRecorderRef.current.state === 'recording') {
        console.log('Stopping MediaRecorder...');
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
    }
    
    // Then stop the audio stream
    if (audioStreamRef?.current) {
        console.log('Stopping audio stream...');
        audioStreamRef.current.getTracks().forEach(track => {
            track.stop();
            track.enabled = false;
        });
        audioStreamRef.current = null;
    }
    
    // Clear the duration interval
    if (durationIntervalRef?.current) {
        console.log('Clearing duration interval...');
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
    }
    
    // Reset recording state
    if (setIsRecording) setIsRecording(false);
    if (setRecordingDuration) setRecordingDuration(0);
    
    // Finally, close the WebSocket connection
    if (webSocketRef?.current) {
        console.log('Closing WebSocket connection...');
        webSocketRef.current.close();
        webSocketRef.current = null;
    }
    
    // Automatically refresh the transcription list after a short delay
    setTimeout(() => {
        const transcriptionList = document.querySelector('.transcription-list');
        if (transcriptionList) {
            const refreshButton = transcriptionList.querySelector('.refresh-button');
            if (refreshButton) {
                refreshButton.click();
            }
        }
    }, 2000);
}; 