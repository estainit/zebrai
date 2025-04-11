import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRecording } from '../context/RecordingContext';
import { Link, useLocation } from 'react-router-dom';
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
    const location = useLocation();

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
                    <Link to="/" className="brand-link">
                        <svg className="home-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                            <path d="M9 22V12h6v10" />
                        </svg>
                        Zebrai
                    </Link>
                    <p className="welcome-text">
                        {isLoggedIn ? `Welcome, ${username}!` : 'Welcome to Zebrai'}
                    </p>
                </div>

                <div className={`nav-links ${isMenuOpen ? 'active' : ''}`}>
                    {isLoggedIn && (
                        <>
                            <div className="menu-item">
                                <button 
                                    className={`menu-button ${activeMenu === 'menu1' ? 'active' : ''}`}
                                    onClick={() => handleMenuClick('menu1')}
                                >
                                    Menu 1
                                </button>
                                {activeMenu === 'menu1' && (
                                    <div className="dropdown-menu">
                                        <Link to="/menu1/submenu1">Submenu 1</Link>
                                        <Link to="/menu1/submenu2">Submenu 2</Link>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className={`menu-button ${activeMenu === 'voices' ? 'active' : ''}`}
                                    onClick={() => handleMenuClick('voices')}
                                >
                                    Voices
                                </button>
                                {activeMenu === 'voices' && (
                                    <div className="dropdown-menu">
                                        <Link to="/voices">All Voices</Link>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className={`menu-button ${activeMenu === 'menu2' ? 'active' : ''}`}
                                    onClick={() => handleMenuClick('menu2')}
                                >
                                    Menu 2
                                </button>
                                {activeMenu === 'menu2' && (
                                    <div className="dropdown-menu">
                                        <a href="#">Submenu 2.1</a>
                                        <a href="#">Submenu 2.2</a>
                                        <a href="#">Submenu 2.3</a>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className="menu-button"
                                    onClick={logout}
                                >
                                    Logout
                                </button>
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