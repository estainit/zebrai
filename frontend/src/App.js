import React, { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid'; // Import uuid
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import TranscriptionList from './components/TranscriptionList';
import Navigation from './components/Navigation';
import './App.css';
import { startRecording, stopRecording } from './services/recordingService';

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
  const [recordingStartTime, setRecordingStartTime] = useState(null);
  const location = useLocation();

  // Refs to hold instances that shouldn't trigger re-renders on change
  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingStartTimeRef = useRef(null);
  const durationIntervalRef = useRef(null);

  const handleStartRecording = async () => {
    if (isRecording) return;
    
    try {
      const recorder = await startRecording({
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
      });
      
      if (recorder) {
        mediaRecorderRef.current = recorder;
      }
    } catch (error) {
      console.error('Error starting recording:', error);
      setError(error.message);
    }
  };

  const handleStopRecording = () => {
    if (!isRecording) return;
    
    try {
      stopRecording({
        mediaRecorderRef,
        webSocketRef,
        audioStreamRef,
        setIsRecording,
        setRecordingDuration,
        durationIntervalRef
      });
    } catch (error) {
      console.error('Error stopping recording:', error);
      setError(error.message);
    }
  };

  // --- Cleanup Effect ---
  useEffect(() => {
    // This runs when the component unmounts
    return () => {
      console.log('App Component unmounting. Cleaning up...');
      if (mediaRecorderRef?.current && mediaRecorderRef.current.state === 'recording') {
        handleStopRecording();
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
