import React, { useState, useRef, useEffect, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid'; // Import uuid
import Login from './components/Login';
import TranscriptionList from './components/TranscriptionList';
import { useAuth } from './context/AuthContext';
import './App.css';

// --- Configuration ---
// Make sure this matches where your backend WebSocket is running
const BACKEND_WS_URL = 'wss://cryptafe.io/ws'; // Always use secure WebSocket in production
const AUDIO_MIME_TYPE = 'audio/webm;codecs=opus'; // Common choice, ensure backend expects this format/extension
const TIMESLICE_MS = 2000; // Send chunks every 2 seconds

function App() {
  const { isLoggedIn, authToken, username, logout, webSocketRef } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState(uuidv4());
  const [recordingDuration, setRecordingDuration] = useState(0);

  // Refs to hold instances that shouldn't trigger re-renders on change
  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingStartTimeRef = useRef(null);
  const durationIntervalRef = useRef(null);

  // --- Media Recording Logic ---
  const startRecording = async () => {
    if (isRecording || !isLoggedIn) return;
    
    // Generate a new session ID for each recording
    const newSessionId = uuidv4();
    setSessionId(newSessionId);
    
    setError('');
    setTranscript(''); // Clear previous transcript
    audioChunksRef.current = []; // Clear chunks
    setRecordingDuration(0);
    recordingStartTimeRef.current = Date.now();

    try {
      // 1. Get audio stream
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;

      // 2. Create MediaRecorder
      const recorder = new MediaRecorder(stream, { mimeType: AUDIO_MIME_TYPE });
      mediaRecorderRef.current = recorder;

      // 3. Connect WebSocket
      if (webSocketRef.current) {
        webSocketRef.current.close();
        webSocketRef.current = null;
      }

      const ws = new WebSocket(`${BACKEND_WS_URL}/${newSessionId}`);
      webSocketRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        // Send token in the connection
        ws.send(JSON.stringify({ type: 'auth', token: authToken }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received WebSocket message:', message);
          
          if (message.type === 'transcript' && message.text) {
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
          } else if (message.type === 'error') {
            console.error('Received error from backend:', message.message);
            setError(`Backend Error: ${message.message}`);
          }
        } catch (e) {
          console.error('Failed to parse message:', event.data, e);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket Error:', event);
        setError('WebSocket connection error. Please check your credentials.');
      };

      ws.onclose = (event) => {
        console.log('WebSocket Disconnected:', event.reason);
        if (event.code === 4001 || event.code === 4002) {
          setError('Authentication failed. Please log in again.');
        }
      };

      // 4. Handle data chunks
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0 && webSocketRef.current?.readyState === WebSocket.OPEN) {
          console.log(`Sending audio chunk: ${event.data.size} bytes`);
          audioChunksRef.current.push(event.data); // Store locally if needed
          webSocketRef.current.send(event.data); // Send blob directly
        } else if (webSocketRef.current?.readyState !== WebSocket.OPEN) {
          console.warn('WebSocket not open. Cannot send audio chunk.');
          // Don't stop recording here, just log the warning
        }
      };

      // 5. Handle recording stop
      recorder.onstop = () => {
        console.log('Media Recorder stopped.');
        if (audioStreamRef.current) {
          audioStreamRef.current.getTracks().forEach(track => track.stop());
          audioStreamRef.current = null;
        }
        setIsRecording(false);
        
        // Clear intervals
        if (durationIntervalRef.current) {
          clearInterval(durationIntervalRef.current);
          durationIntervalRef.current = null;
        }
      };

      // 6. Start recording with timeslice
      recorder.start(TIMESLICE_MS);
      setIsRecording(true);
      console.log('Recording started...');
      
      // 7. Set up duration tracking
      durationIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - recordingStartTimeRef.current) / 1000);
        setRecordingDuration(elapsed);
      }, 1000);

    } catch (err) {
      console.error('Error starting recording:', err);
      setError(`Error: ${err.message}`);
      // Cleanup on error
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
        audioStreamRef.current = null;
      }
      setIsRecording(false);
      
      // Clear intervals
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
    }
  };

  const stopRecording = () => {
    if (!isRecording || !mediaRecorderRef.current) return;
    console.log('Stopping recording...');
    
    // Stop the media recorder
    if (mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    
    // Close WebSocket connection after a short delay to ensure all data is sent
    setTimeout(() => {
      if (webSocketRef.current) {
        webSocketRef.current.close();
        webSocketRef.current = null;
      }
      
      // Ensure all resources are properly cleaned up
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
        audioStreamRef.current = null;
      }
      
      // Clear intervals
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
      
      // Reset recording state
      setIsRecording(false);
    }, 1000);
  };

  // --- Cleanup Effect ---
  useEffect(() => {
    // This runs when the component unmounts
    return () => {
      console.log('App Component unmounting. Cleaning up...');
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
      }
      
      // Clear intervals
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
    };
  }, []); // Empty dependency array means run only on mount and unmount

  // Format duration for display
  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isLoggedIn) {
    return <Login />;
  }

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <h1>Real-time Transcription Assistant</h1>
          <div className="user-info">
            <span>Welcome, {username}</span>
            <button onClick={logout} className="logout-button">Logout</button>
          </div>
        </div>
        <button onClick={isRecording ? stopRecording : startRecording}>
          {isRecording ? 'Stop Recording' : 'Start Recording'}
        </button>
        <p>Status: {isRecording ? 'Recording...' : 'Idle'}</p>
        {isRecording && <p>Duration: {formatDuration(recordingDuration)}</p>}
        {error && <p style={{ color: 'red' }}>Error: {error}</p>}
        <div className="transcript-container">
          <h2>Transcript:</h2>
          <div className="transcript-text" style={{ 
            whiteSpace: 'pre-wrap', 
            wordBreak: 'break-word',
            maxHeight: '300px',
            overflowY: 'auto',
            padding: '10px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            {transcript || '...'}
          </div>
        </div>
        
        {/* Add the TranscriptionList component */}
        <div className="transcription-list-container">
          <h2>Transcription History</h2>
          <TranscriptionList credentials={authToken} />
        </div>
      </header>
    </div>
  );
}

export default App;
