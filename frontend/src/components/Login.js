import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        // Check for error in URL
        const params = new URLSearchParams(location.search);
        const error = params.get('error');
        if (error) {
            setError(error);
        }

        // Handle messages from popup window
        const handleMessage = (event) => {
            if (event.data.type === 'oauth-success') {
                // Store the token and username
                localStorage.setItem('authToken', event.data.token);
                localStorage.setItem('username', event.data.username);
                // Navigate to home
                navigate('/');
            } else if (event.data.type === 'oauth-error') {
                setError(event.data.error);
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [location, navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(username, password);
            navigate('/');
        } catch (err) {
            setError(err.message);
        }
    };

    const handleGoogleLogin = () => {
        // Open Google OAuth popup
        const width = 600;
        const height = 600;
        const left = window.screen.width / 2 - width / 2;
        const top = window.screen.height / 2 - height / 2;
        
        window.open(
            'https://cryptafe.io/api/auth/google',
            'Google OAuth',
            `width=${width},height=${height},left=${left},top=${top}`
        );
    };

    return (
        <div className="login-container">
            <div className="login-box">
                <h2>Login</h2>
                {error && <div className="error-message">{error}</div>}
                
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="username">Username</label>
                        <input
                            type="text"
                            id="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </div>
                    
                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <input
                            type="password"
                            id="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    
                    <button type="submit" className="login-button">
                        Login
                    </button>
                </form>
                
                <div className="divider">
                    <span>OR</span>
                </div>
                
                <button 
                    onClick={handleGoogleLogin}
                    className="google-login-button"
                >
                    <img 
                        src="/google-icon.svg" 
                        alt="Google"
                        className="google-icon"
                    />
                    Continue with Google
                </button>
            </div>
        </div>
    );
};

export default Login; 