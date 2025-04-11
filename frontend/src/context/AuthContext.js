import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [authToken, setAuthToken] = useState(null);
    const [username, setUsername] = useState('');
    const [webSocketRef, setWebSocketRef] = useState(null);

    useEffect(() => {
        // Check for token in URL (Google OAuth callback)
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');
        const username = params.get('username');

        if (token && username) {
            // Store the token and username
            localStorage.setItem('authToken', token);
            localStorage.setItem('username', username);
            setAuthToken(token);
            setUsername(username);
            setIsLoggedIn(true);
            
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
        } else {
            // Check for existing token in localStorage
            const storedToken = localStorage.getItem('authToken');
            const storedUsername = localStorage.getItem('username');
            if (storedToken && storedUsername) {
                setAuthToken(storedToken);
                setUsername(storedUsername);
                setIsLoggedIn(true);
            }
        }
    }, []);

    const login = async (username, password) => {
        try {
            const response = await fetch('https://cryptafe.io/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            if (!response.ok) {
                throw new Error('Login failed');
            }

            const data = await response.json();
            localStorage.setItem('authToken', data.token);
            localStorage.setItem('username', data.username);
            setAuthToken(data.token);
            setUsername(data.username);
            setIsLoggedIn(true);
        } catch (error) {
            throw new Error('Login failed: ' + error.message);
        }
    };

    const logout = () => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        setAuthToken(null);
        setUsername('');
        setIsLoggedIn(false);
        
        // Close WebSocket connection if exists
        if (webSocketRef) {
            webSocketRef.close();
            setWebSocketRef(null);
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
        login,
        logout,
        webSocketRef,
        setWebSocketRef,
        handleSessionExpired,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}; 