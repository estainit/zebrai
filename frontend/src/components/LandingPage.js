import React from 'react';
import { useTranslation } from 'react-i18next';
import './LandingPage.css';

const LandingPage = () => {
  const { t } = useTranslation();

  return (
    <div className="landing-page">
      <div className="welcome-content">
        <h1>{t('landing.welcome')}</h1>
        <p>{t('landing.description')}</p>
      </div>
      
      <div className="features-grid">
        <div className="feature-card import-history">
          <h2>Import History</h2>
          <p>Import and manage your previous conversations and data</p>
        </div>
        
        <div className="feature-card new-client">
          <h2>New Client</h2>
          <p>Start a new conversation with a fresh perspective</p>
        </div>
        
        <div className="feature-card manage">
          <h2>Manage</h2>
          <p>Organize and control your conversations and settings</p>
        </div>
        
        <div className="feature-card settings">
          <h2>Settings</h2>
          <p>Customize your experience and preferences</p>
        </div>
      </div>
    </div>
  );
};

export default LandingPage; 