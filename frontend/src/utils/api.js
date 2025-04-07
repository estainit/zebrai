import { useAuth } from '../context/AuthContext';

/**
 * Wrapper for fetch that handles authentication and error responses
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @param {Function} handleSessionExpired - Function to call when session expires
 * @returns {Promise} - Fetch response
 */
export const fetchWithAuth = async (url, options = {}, handleSessionExpired) => {
  // Get the auth token from localStorage
  const token = localStorage.getItem('authToken');
  
  // Add authorization header if token exists
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...options.headers
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // Make the request
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  // Handle 401 Unauthorized (session expired)
  if (response.status === 401) {
    console.log('Session expired (401 Unauthorized)');
    if (handleSessionExpired) {
      handleSessionExpired();
    }
    throw new Error('Session expired. Please log in again.');
  }
  
  return response;
};

/**
 * Custom hook for making authenticated API requests
 * @returns {Object} - API methods
 */
export const useApi = () => {
  const { handleSessionExpired } = useAuth();
  
  return {
    get: (url, options = {}) => fetchWithAuth(url, { ...options, method: 'GET' }, handleSessionExpired),
    post: (url, data, options = {}) => fetchWithAuth(url, { 
      ...options, 
      method: 'POST',
      body: JSON.stringify(data)
    }, handleSessionExpired),
    put: (url, data, options = {}) => fetchWithAuth(url, { 
      ...options, 
      method: 'PUT',
      body: JSON.stringify(data)
    }, handleSessionExpired),
    delete: (url, options = {}) => fetchWithAuth(url, { ...options, method: 'DELETE' }, handleSessionExpired)
  };
}; 