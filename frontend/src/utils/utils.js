/**
 * Detects the client type based on the user agent string
 * @returns {string} The detected client type ('ios', 'mac', 'windows', 'linux', 'android', or 'unknown')
 */
export const getClientType = () => {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
        return 'ios';
    } else if (userAgent.includes('macintosh')) {
        return 'mac';
    } else if (userAgent.includes('windows')) {
        return 'windows';
    } else if (userAgent.includes('linux')) {
        return 'linux';
    } else if (userAgent.includes('android')) {
        return 'android';
    }
    
    return 'unknown';
};

/**
 * Checks if the current device is an iOS device
 * @returns {boolean} True if the device is iOS, false otherwise
 */
export const isIOS = () => {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
};

/**
 * Gets the supported MIME type for audio recording
 * @returns {string|null} The supported MIME type or null if no supported type is found
 */
export const getSupportedMimeType = () => {
    const types = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        'audio/wav'
    ];
    
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
            console.log('Using MIME type:', type);
            return type;
        }
    }
    
    // If no supported type is found, return null to use browser default
    console.warn('No supported MIME type found, using browser default');
    return null;
};

/**
 * Gets iOS-specific audio settings
 * @returns {Object} The audio settings for iOS devices
 */
export const getIOSAudioSettings = () => {
    return {
        mimeType: 'audio/mp4',
        audioBitsPerSecond: 128000
    };
}; 