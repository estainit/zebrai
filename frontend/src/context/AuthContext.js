import React, { createContext, useState, useContext, useEffect, useRef } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authToken, setAuthToken] = useState(null);
  const [username, setUsername] = useState(null);
  const [error, setError] = useState('');
  const webSocketRef = useRef(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Check for stored credentials on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('authToken');
    const storedUsername = localStorage.getItem('username');
    
    if (storedToken && storedUsername) {
      // If we have stored credentials, restore the session
      setAuthToken(storedToken);
      setUsername(storedUsername);
      setIsLoggedIn(true);
    }
  }, []);

  const cleanupWebSocket = () => {
    if (webSocketRef.current) {
      webSocketRef.current.close();
      webSocketRef.current = null;
    }
  };

  const login = async (username, password) => {
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ username, password }),
        mode: 'cors',
        credentials: 'include'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      
      if (data.access_token) {
        // Store the session data
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('username', data.username);
        
        // Update the state
        setAuthToken(data.access_token);
        setUsername(data.username);
        setIsLoggedIn(true);
        setError('');
        setSessionExpired(false);
        
        return true;
      }
      
      throw new Error('No access token received');
    } catch (err) {
      console.error('Login error:', err);
      setError(err.message || 'Failed to connect to the server');
      setIsLoggedIn(false);
      setAuthToken(null);
      setUsername(null);
      return false;
    }
  };

  const logout = () => {
    cleanupWebSocket();
    setAuthToken(null);
    setUsername(null);
    setIsLoggedIn(false);
    setError('');
    setSessionExpired(false);
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
  };

  // Handle session expiration
  const handleSessionExpired = () => {
    console.log('Session expired, logging out user');
    setSessionExpired(true);
    logout();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupWebSocket();
    };
  }, []);

  const value = {
    isLoggedIn,
    authToken,
    username,
    error,
    login,
    logout,
    setError,
    webSocketRef,
    sessionExpired,
    handleSessionExpired
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 