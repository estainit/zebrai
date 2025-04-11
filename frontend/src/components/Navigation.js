import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRecording } from '../context/RecordingContext';
import './Navigation.css';

const Navigation = () => {
    const { isLoggedIn, username, logout, webSocketRef, handleSessionExpired, authToken } = useAuth();
    const { 
        isRecording, 
        recordingDuration, 
        handleStartRecording, 
        handleStopRecording 
    } = useRecording();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [activeMenu, setActiveMenu] = useState(null);

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen);
    };

    const handleMenuClick = (menu) => {
        setActiveMenu(activeMenu === menu ? null : menu);
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
                                    onClick={isRecording ? handleStopRecording : () => handleStartRecording(authToken, webSocketRef, handleSessionExpired)}
                                    disabled={!isLoggedIn}
                                >
                                    {isRecording ? 'Stop' : 'Start Recording'}
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