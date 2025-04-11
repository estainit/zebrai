import React from 'react';
import './GoogleLoginButton.css';

const GoogleLoginButton = () => {
  const handleGoogleLogin = () => {
    // Redirect to backend Google OAuth endpoint
    window.location.href = '/api/auth/google';
  };

  return (
    <button 
      className="google-login-button"
      onClick={handleGoogleLogin}
    >
      <img 
        src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
        alt="Google logo"
        className="google-logo"
      />
      Continue with Google
    </button>
  );
};

export default GoogleLoginButton; 