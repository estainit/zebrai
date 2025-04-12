import Cookies from 'js-cookie';

const LANGUAGE_COOKIE_KEY = 'user_language';
const LANGUAGE_STORAGE_KEY = 'user_language';

/**
 * Detects user's preferred language following this priority:
 * 1. User Profile Setting (from API)
 * 2. LocalStorage/SessionStorage
 * 3. Cookie
 * 4. Browser language
 * 
 * @param {string} userLanguage - Language from user profile (optional)
 * @returns {string} Detected language code
 */
export const detectLanguage = (userLanguage = null) => {
    // 1. Check user profile language first
    if (userLanguage) {
        return userLanguage;
    }

    // 2. Check LocalStorage/SessionStorage
    const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY) || 
                          sessionStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (storedLanguage) {
        return storedLanguage;
    }

    // 3. Check Cookie
    const cookieLanguage = Cookies.get(LANGUAGE_COOKIE_KEY);
    if (cookieLanguage) {
        return cookieLanguage;
    }

    // 4. Use browser language
    const browserLanguage = navigator.language || navigator.userLanguage;
    return browserLanguage.split('-')[0]; // Return only the language code (e.g., 'en' from 'en-US')
};

/**
 * Saves the user's language preference to all available storage methods
 * @param {string} language - Language code to save
 * @param {boolean} remember - Whether to remember the choice permanently
 */
export const saveLanguagePreference = (language, remember = true) => {
    // Save to LocalStorage if remember is true, otherwise use SessionStorage
    if (remember) {
        localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } else {
        sessionStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    }

    // Save to cookie with 1 year expiration
    Cookies.set(LANGUAGE_COOKIE_KEY, language, { expires: 365 });

    // Update document language attribute
    document.documentElement.lang = language;
};

/**
 * Clears all stored language preferences
 */
export const clearLanguagePreference = () => {
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    sessionStorage.removeItem(LANGUAGE_STORAGE_KEY);
    Cookies.remove(LANGUAGE_COOKIE_KEY);
}; 