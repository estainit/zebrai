import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './Navigation.css';
import { v4 as uuidv4 } from 'uuid';

// WebSocket configuration
const BACKEND_WS_URL = 'wss://cryptafe.io/ws';

const Navigation = () => {
    const { isLoggedIn, username, logout, webSocketRef, handleSessionExpired, authToken } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [activeMenu, setActiveMenu] = useState(null);
    const [isRecording, setIsRecording] = useState(false);
    const [recordingDuration, setRecordingDuration] = useState(0);
    const [recordingStartTime, setRecordingStartTime] = useState(null);

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen);
    };

    const handleMenuClick = (menu) => {
        setActiveMenu(activeMenu === menu ? null : menu);
    };

    const startRecording = async () => {
        if (isRecording || !isLoggedIn) return;
        
        try {
            // Generate a new session ID for each recording
            const sessionId = uuidv4();
            
            // Create WebSocket connection first
            const ws = new WebSocket(`${BACKEND_WS_URL}/${sessionId}`);
            webSocketRef.current = ws;
            
            // Wait for WebSocket to be ready
            await new Promise((resolve, reject) => {
                ws.onopen = () => {
                    console.log('WebSocket connected');
                    // Send token in the connection
                    ws.send(JSON.stringify({ type: 'auth', token: authToken }));
                    resolve();
                };
                
                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };
            });

            // Now get the audio stream
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && webSocketRef.current?.readyState === WebSocket.OPEN) {
                    webSocketRef.current.send(event.data);
                }
            };

            mediaRecorder.start(1000); // Send chunks every second
            setIsRecording(true);
            setRecordingStartTime(Date.now());
            
            // Update duration every second
            const interval = setInterval(() => {
                setRecordingDuration(Math.floor((Date.now() - recordingStartTime) / 1000));
            }, 1000);

            // Cleanup on stop
            mediaRecorder.onstop = () => {
                clearInterval(interval);
                stream.getTracks().forEach(track => track.stop());
                if (webSocketRef.current) {
                    webSocketRef.current.close();
                    webSocketRef.current = null;
                }
                setIsRecording(false);
                setRecordingDuration(0);
            };
        } catch (err) {
            console.error('Error starting recording:', err);
            if (webSocketRef.current) {
                webSocketRef.current.close();
                webSocketRef.current = null;
            }
            setIsRecording(false);
            setRecordingDuration(0);
        }
    };

    const stopRecording = () => {
        if (!isRecording) return;
        setIsRecording(false);
        setRecordingDuration(0);
    };

    const formatDuration = (seconds) => {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    return (
        <nav className="navigation">
            <div className="nav-container">
                <div className="nav-brand">
                    <h1>Zebrai</h1>
                    <p className="welcome-text">
                        {isLoggedIn ? `Welcome, ${username}!` : 'Welcome to Zebrai'}
                    </p>
                </div>

                <div className={`nav-links ${isMenuOpen ? 'active' : ''}`}>
                    {isLoggedIn && (
                        <>
                            <div className="menu-item">
                                <button 
                                    className="menu-button"
                                    onClick={() => handleMenuClick('menu1')}
                                >
                                    Menu 1
                                </button>
                                {activeMenu === 'menu1' && (
                                    <div className="submenu">
                                        <a href="#">Submenu 1.1</a>
                                        <a href="#">Submenu 1.2</a>
                                        <a href="#">Submenu 1.3</a>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className="menu-button"
                                    onClick={() => handleMenuClick('menu2')}
                                >
                                    Menu 2
                                </button>
                                {activeMenu === 'menu2' && (
                                    <div className="submenu">
                                        <a href="#">Submenu 2.1</a>
                                        <a href="#">Submenu 2.2</a>
                                        <a href="#">Submenu 2.3</a>
                                    </div>
                                )}
                            </div>

                            <div className="record-container">
                                <button 
                                    className={`record-button ${isRecording ? 'recording' : ''}`}
                                    onClick={isRecording ? stopRecording : startRecording}
                                    disabled={!isLoggedIn}
                                >
                                    {isRecording ? 'Stop Recording' : 'Start Recording'}
                                    {isRecording && (
                                        <>
                                            <span className="recording-indicator"></span>
                                            <span className="recording-timer">{formatDuration(recordingDuration)}</span>
                                        </>
                                    )}
                                </button>
                            </div>

                            <button className="logout-button" onClick={logout}>
                                Logout
                            </button>
                        </>
                    )}
                </div>

                <button 
                    className="mobile-menu-button"
                    onClick={toggleMenu}
                    aria-label="Toggle menu"
                >
                    <span className="menu-icon"></span>
                </button>
            </div>
        </nav>
    );
};

export default Navigation; 