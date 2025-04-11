import React, { createContext, useContext, useState, useRef } from 'react';
import { startRecording, stopRecording } from '../services/recordingService';

const RecordingContext = createContext();

export const RecordingProvider = ({ children }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [recordingStartTime, setRecordingStartTime] = useState(null);
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');

  // Refs
  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const durationIntervalRef = useRef(null);

  const handleStartRecording = async (authToken, webSocketRef, handleSessionExpired) => {
    if (isRecording) return;
    
    try {
      const recorder = await startRecording({
        isLoggedIn: true,
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
        webSocketRef: null, // This will be provided by the component
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

  return (
    <RecordingContext.Provider value={{
      isRecording,
      recordingDuration,
      recordingStartTime,
      error,
      transcript,
      handleStartRecording,
      handleStopRecording,
      mediaRecorderRef,
      audioStreamRef,
      audioChunksRef,
      durationIntervalRef
    }}>
      {children}
    </RecordingContext.Provider>
  );
};

export const useRecording = () => {
  const context = useContext(RecordingContext);
  if (!context) {
    throw new Error('useRecording must be used within a RecordingProvider');
  }
  return context;
}; 