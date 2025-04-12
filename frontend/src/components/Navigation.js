import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRecording } from '../context/RecordingContext';
import { Link, redirect, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../hooks/useLanguage';
import { useUserProfile } from '../modules/UserProfile';
import './Navigation.css';

const Navigation = () => {
    const { isLoggedIn, username, logout, webSocketRef, handleSessionExpired, authToken, userProfile } = useAuth();
    const { 
        isRecording, 
        recordingDuration, 
        handleStartRecording, 
        handleStopRecording 
    } = useRecording();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [activeMenu, setActiveMenu] = useState(null);
    const location = useLocation();
    const navigate = useNavigate();
    const { t, i18n } = useTranslation();
    const { currentLanguage, changeLanguage } = useLanguage(isLoggedIn ? userProfile?.lang : null);
    const { updateUserLanguage } = useUserProfile();

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

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const handleLanguageChange = async (e) => {
        const newLanguage = e.target.value;
        try {
            // Update language in the database
            const success = await updateUserLanguage(newLanguage);
            if (success) {
                // Change the UI language immediately
                changeLanguage(newLanguage, true);
                // Force a re-render of the translations
                await i18n.reloadResources([newLanguage]);
            } else {
                console.error('Failed to update language preference');
            }
        } catch (error) {
            console.error('Error updating language:', error);
        }
    };

    return (
        <nav className="navigation">
            <div className="nav-container">
                <div className="nav-brand">
                    <Link to="/" className="brand-link">
                        <img src="/vardastai-logo-70x70.png" alt="Home" className="vardastai-icon" />
                        VardastAI
                    </Link>
                    <p className="welcome-text">
                        {isLoggedIn ? t('landing.welcome', { username }) : t('landing.welcome_guest')}
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
                                    {t('navigation.menu1')}
                                </button>
                                {activeMenu === 'menu1' && (
                                    <div className="dropdown-menu">
                                        <Link to="/menu1/submenu1">{t('navigation.submenu1')}</Link>
                                        <Link to="/menu1/submenu2">{t('navigation.submenu2')}</Link>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className={`menu-button ${activeMenu === 'voices' ? 'active' : ''}`}
                                    onClick={() => handleMenuClick('voices')}
                                >
                                    {t('navigation.voices')}
                                </button>
                                {activeMenu === 'voices' && (
                                    <div className="dropdown-menu">
                                        <Link to="/voices">{t('navigation.all_voices')}</Link>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className={`menu-button ${activeMenu === 'menu2' ? 'active' : ''}`}
                                    onClick={() => handleMenuClick('menu2')}
                                >
                                    {t('navigation.menu2')}
                                </button>
                                {activeMenu === 'menu2' && (
                                    <div className="dropdown-menu">
                                        <a href="#">{t('navigation.submenu2_1')}</a>
                                        <a href="#">{t('navigation.submenu2_2')}</a>
                                        <a href="#">{t('navigation.submenu2_3')}</a>
                                    </div>
                                )}
                            </div>

                            <div className="menu-item">
                                <button 
                                    className="menu-button"
                                    onClick={handleLogout}
                                >
                                    {t('common.logout')}
                                </button>
                            </div>

                            <div className="record-container">
                                <button 
                                    className={`record-button ${isRecording ? 'recording' : ''}`}
                                    onClick={isRecording ? handleStopRecording : () => handleStartRecording(authToken, webSocketRef, handleSessionExpired)}
                                    disabled={!isLoggedIn}
                                >
                                    {isRecording ? t('recording.stop') : t('recording.start')}
                                    {isRecording && (
                                        <>
                                            <span className="recording-indicator"></span>
                                            <span className="recording-timer">{formatDuration(recordingDuration)}</span>
                                        </>
                                    )}
                                </button>
                            </div>

                            <div className="language-selector">
                                <select 
                                    value={currentLanguage} 
                                    onChange={handleLanguageChange}
                                    className="language-dropdown"
                                >
                                    <option value="en">English</option>
                                    <option value="ar">العربية</option>
                                    <option value="fa">پارسی</option>
                                    <option value="it">Italiano</option>
                                    <option value="es">Español</option>
                                </select>
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