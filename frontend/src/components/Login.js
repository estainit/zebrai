import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login, handleSocialLogin } = useAuth();
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
        const handleMessage = async (event) => {
            if (event.data.type === 'oauth-success') {
                await handleSocialLogin(event.data.token, event.data.username);
            } else if (event.data.type === 'oauth-error') {
                setError(event.data.error);
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [location, handleSocialLogin]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(username, password);
            window.location.href = '/';
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
            'https://vardastai.com/api/auth/google',
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
                        src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
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