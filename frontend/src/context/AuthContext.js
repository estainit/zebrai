import React, { createContext, useContext, useState, useEffect, useRef } from 'react';

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
            const storedToken = localStorage.getItem('authToken');
            const storedUsername = localStorage.getItem('username');
            const storedProfile = localStorage.getItem('userProfile');
            
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
        localStorage.setItem('authToken', token);
        localStorage.setItem('username', username);
        setAuthToken(token);
        setUsername(username);
        setIsLoggedIn(true);
        
        await fetchUserProfile(token);
        
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
    };

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
            localStorage.setItem('authToken', data.access_token);
            localStorage.setItem('username', data.username);
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
            localStorage.setItem('userProfile', JSON.stringify(profile));
            
            // Redirect to home page
            window.location.href = '/';
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('userProfile');
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

    const value = {
        isLoggedIn,
        authToken,
        username,
        userProfile,
        webSocketRef,
        login,
        logout,
        handleSessionExpired,
        handleSocialLogin
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}; 