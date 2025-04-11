import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RecordingProvider } from './context/RecordingContext';
import Login from './components/Login';
import TranscriptionList from './components/TranscriptionList';
import Navigation from './components/Navigation';
import './App.css';

// --- Configuration ---
// Make sure this matches where your backend WebSocket is running
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

const PrivateRoute = ({ children }) => {
  const { isLoggedIn } = useAuth();
  const location = useLocation();

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const AppContent = () => {
  const { isLoggedIn } = useAuth();
  const location = useLocation();

  return (
    <div className="app">
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
            path="/voices" 
            element={
              <PrivateRoute>
                <TranscriptionList />
              </PrivateRoute>
            } 
          />
          <Route 
            path="/" 
            element={
              <PrivateRoute>
                <div className="home-content">
                  <h1>Welcome to Zebrai</h1>
                  <p>دستیار زبر و زرنگ شما در مطب</p>
                </div>
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
        <RecordingProvider>
          <AppContent />
        </RecordingProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
