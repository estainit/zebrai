import React, { createContext, useContext, useState, useEffect, useRef } from 'react';

import { useUserProfile } from '../modules/UserProfile';
import { STORAGE_AUTH_TOKEN_KEY, STORAGE_USERNAME_KEY, STORAGE_USER_PROFILE_KEY } from '../config/constants';
const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [authToken, setAuthToken] = useState(null);
    const [username, setUsername] = useState('');
    const [userProfile, setUserProfile] = useState(null);
    const webSocketRef = useRef(null);

    useEffect(() => {
        // Check for token in URL (Google OAuth callback)
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');
        const username = params.get('username');

        if (token && username) {
            // Handle social login callback
            handleSocialLogin(token, username);
        } else{
            // Check for existing token in localStorage
            const storedToken = localStorage.getItem(STORAGE_AUTH_TOKEN_KEY);
            const storedUsername = localStorage.getItem(STORAGE_USERNAME_KEY);
            const storedProfile = localStorage.getItem(STORAGE_USER_PROFILE_KEY);
            
            if (storedToken && storedUsername) {
                setAuthToken(storedToken);
                setUsername(storedUsername);
                if (storedProfile) {
                    setUserProfile(JSON.parse(storedProfile));
                }
                setIsLoggedIn(true);
            }
        }
    }, []);

    const handleSocialLogin = async (token, username) => {
        // Store the token and username
        localStorage.setItem(STORAGE_AUTH_TOKEN_KEY, token);
        localStorage.setItem(STORAGE_USERNAME_KEY, username);
        setAuthToken(token);
        setUsername(username);
        setIsLoggedIn(true);
        
        await useUserProfile.fetchUserProfile(token);
        
        // Remove token from URL
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // If this is a popup window, close it and refresh the opener
        if (window.opener) {
            window.opener.location.href = '/';
            window.close();
        } else {
            // If not a popup, just redirect to home
            window.location.href = '/';
        }
    };
/* 
    const fetchUserProfile = async (token) => {
        try {
            const response = await fetch('https://vardastai.com/api/user/profile', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (!response.ok) {
                console.error('Profile fetch failed:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('Error response body:', errorText);
                return;
            }
            
            const profile = await response.json();
            setUserProfile(profile);
            localStorage.setItem('userProfile', JSON.stringify(profile));
        } catch (error) {
            console.error('Error fetching user profile:', error);
        }
    }; */

    const login = async (username, password) => {
        try {
            const response = await fetch('https://vardastai.com/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Login failed');
            }

            const data = await response.json();
            
            // Handle username/password login response
            localStorage.setItem(STORAGE_AUTH_TOKEN_KEY, data.access_token);
            localStorage.setItem(STORAGE_USERNAME_KEY, data.username);
            setAuthToken(data.access_token);
            setUsername(data.username);
            setIsLoggedIn(true);
            
            // Set user profile from login response
            const profile = {
                username: data.username,
                role: data.role,
                lang: data.lang,
                conf: data.conf
            };
            setUserProfile(profile);
            localStorage.setItem(STORAGE_USER_PROFILE_KEY, JSON.stringify(profile));
            
            // Redirect to home page
            window.location.href = '/';
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem(STORAGE_AUTH_TOKEN_KEY);
        localStorage.removeItem(STORAGE_USERNAME_KEY);
        localStorage.removeItem(STORAGE_USER_PROFILE_KEY);
        setAuthToken(null);
        setUsername('');
        setUserProfile(null);
        setIsLoggedIn(false);
        
        // Close WebSocket connection if exists
        if (webSocketRef.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
        }
        
        window.location.href = '/login';
    };

    const handleSessionExpired = () => {
        logout();
    };

    const updateUserLanguage = async (lang) => {
        try {
            const response = await fetch('https://vardastai.com/api/user/profile/language', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ lang })
            });

            if (!response.ok) {
                throw new Error('Failed to update language preference');
            }

            // Update local profile
            const updatedProfile = { ...userProfile, lang };
            setUserProfile(updatedProfile);
            localStorage.setItem(STORAGE_USER_PROFILE_KEY, JSON.stringify(updatedProfile));
            
            return true;
        } catch (error) {
            console.error('Error updating language:', error);
            return false;
        }
    };

    const value = {
        isLoggedIn,
        authToken,
        username,
        userProfile,
        webSocketRef,
        login,
        logout,
        handleSessionExpired,
        handleSocialLogin,
        updateUserLanguage
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}; 