import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { detectLanguage, saveLanguagePreference } from '../utils/language';

/**
 * Custom hook for language management
 * @param {string} userLanguage - Language from user profile
 * @returns {Object} Language management functions and state
 */
export const useLanguage = (userLanguage = null) => {
    const { i18n } = useTranslation();
    const [currentLanguage, setCurrentLanguage] = useState(detectLanguage(userLanguage));

    useEffect(() => {
        // Initialize language when user profile language changes
        const detectedLanguage = detectLanguage(userLanguage);
        setCurrentLanguage(detectedLanguage);
        i18n.changeLanguage(detectedLanguage);
    }, [userLanguage, i18n]);

    const changeLanguage = (language, remember = true) => {
        setCurrentLanguage(language);
        i18n.changeLanguage(language);
        saveLanguagePreference(language, remember);
    };

    return {
        currentLanguage,
        changeLanguage,
        isLanguage: (lang) => currentLanguage === lang
    };
}; 