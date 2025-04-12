import { useAuth } from '../context/AuthContext';
import { STORAGE_USER_PROFILE_KEY } from '../config/constants';

export const fetchUserProfile = async (token) => {
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
            return null;
        }
        
        const profile = await response.json();
        localStorage.setItem(STORAGE_USER_PROFILE_KEY, JSON.stringify(profile));
        return profile;
    } catch (error) {
        console.error('Error fetching user profile:', error);
        return null;
    }
};

export const useUserProfile = () => {
    const { authToken } = useAuth();

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
            
            return true;
        } catch (error) {
            console.error('Error updating language:', error);
            return false;
        }
    };

    return {
        updateUserLanguage,
        fetchUserProfile: (token) => fetchUserProfile(token)
    };
};

/*         // Update local profile
        const updatedProfile = { ...userProfile, lang };
        setUserProfile(updatedProfile);
        localStorage.setItem('userProfile', JSON.stringify(updatedProfile)); 
        */
        