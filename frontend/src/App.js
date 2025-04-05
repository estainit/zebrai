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
  const [sessionId] = useState(uuidv4());

  // Refs to hold instances that shouldn't trigger re-renders on change
  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioChunksRef = useRef([]);

  // --- Media Recording Logic ---
  const startRecording = async () => {
    if (isRecording || !isLoggedIn) return;
    setError('');
    setTranscript(''); // Clear previous transcript
    audioChunksRef.current = []; // Clear chunks

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

      const ws = new WebSocket(`${BACKEND_WS_URL}/${sessionId}`);
      webSocketRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        // Send token in the connection
        ws.send(JSON.stringify({ type: 'auth', token: authToken }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.transcript) {
            console.log('Received transcript:', message.transcript);
            setTranscript((prev) => prev + message.transcript + ' ');
          } else if (message.error) {
            console.error('Received error from backend:', message.error);
            setError(`Backend Error: ${message.error}`);
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
        console.log('MediaRecorder stopped.');
        if (audioStreamRef.current) {
          audioStreamRef.current.getTracks().forEach(track => track.stop());
          audioStreamRef.current = null;
        }
        setIsRecording(false);
      };

      // 6. Start recording with timeslice
      recorder.start(TIMESLICE_MS);
      setIsRecording(true);
      console.log('Recording started...');

    } catch (err) {
      console.error('Error starting recording:', err);
      setError(`Error: ${err.message}`);
      // Cleanup on error
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
        audioStreamRef.current = null;
      }
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (!isRecording || !mediaRecorderRef.current) return;
    console.log('Stopping recording...');
    mediaRecorderRef.current.stop(); // This will trigger onstop handler
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
    };
  }, []); // Empty dependency array means run only on mount and unmount

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
        {error && <p style={{ color: 'red' }}>Error: {error}</p>}
        <div className="transcript-container">
          <h2>Transcript:</h2>
          <p>{transcript || '...'}</p>
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
