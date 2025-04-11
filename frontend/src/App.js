import React, { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid'; // Import uuid
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import TranscriptionList from './components/TranscriptionList';
import Navigation from './components/Navigation';
import './App.css';

// --- Configuration ---
// Make sure this matches where your backend WebSocket is running
const BACKEND_WS_URL = 'wss://cryptafe.io/ws'; // Always use secure WebSocket in production
const TIMESLICE_MS = 2000; // Send chunks every 2 seconds
// Note: The backend is configured to transcribe after every 10 chunks (CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION)
// This means transcription will occur approximately every 20 seconds (10 chunks * 2 seconds per chunk)

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

const PrivateRoute = ({ children }) => {
  const { isLoggedIn } = useAuth();
  const location = useLocation();

  if (!isLoggedIn) {
    // Redirect to login but save the attempted URL
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const AppContent = () => {
  const { isLoggedIn, authToken, username, logout, webSocketRef, handleSessionExpired } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState('');
  const [recordingDuration, setRecordingDuration] = useState(0);
  const location = useLocation();

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
    
    setError('');
    setTranscript(''); // Clear previous transcript
    audioChunksRef.current = []; // Clear chunks
    setRecordingDuration(0);
    recordingStartTimeRef.current = Date.now();

    try {
      // 1. Get audio stream
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;

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
      mediaRecorderRef.current = recorder;

      // 3. Connect WebSocket
      if (webSocketRef.current) {
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
            if (message.message.includes('Session expired') || message.message.includes('Invalid token')) {
              handleSessionExpired();
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
        setError('WebSocket connection error. Please check your credentials.');
      };

      ws.onclose = (event) => {
        console.log('WebSocket Disconnected:', event.reason);
        if (event.code === 4001 || event.code === 4002) {
          setError('Authentication failed. Please log in again.');
          handleSessionExpired();
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

  return (
    <div className="App">
      <Navigation />
      <main className="main-content">
        <Routes>
          <Route 
            path="/login" 
            element={
              isLoggedIn ? (
                <Navigate to="/" replace />
              ) : (
                <Login />
              )
            } 
          />
          <Route 
            path="/" 
            element={
              <PrivateRoute>
                <TranscriptionList />
              </PrivateRoute>
            } 
          />
          <Route 
            path="*" 
            element={
              <Navigate to={isLoggedIn ? "/" : "/login"} replace />
            } 
          />
        </Routes>
      </main>
    </div>
  );
};

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}

export default App;
