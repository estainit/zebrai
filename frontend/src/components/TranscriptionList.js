import React, { useState, useEffect, useRef, useCallback } from 'react';
import './TranscriptionList.css';
import { FaPlay, FaPause, FaStop, FaTrash, FaSync, FaAngleDoubleLeft, FaAngleLeft, FaAngleRight, FaAngleDoubleRight } from 'react-icons/fa';
import { MdFirstPage, MdLastPage, MdNavigateBefore, MdNavigateNext } from 'react-icons/md';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';

const API_URL = 'https://vardastai.com';

const TranscriptionList = () => {
    const { authToken, handleSessionExpired } = useAuth();
    const [transcriptions, setTranscriptions] = useState([]);
    const [selectedIds, setSelectedIds] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [hasMore, setHasMore] = useState(true);
    const [perPage, setPerPage] = useState(10);
    const [timeFilter, setTimeFilter] = useState(() => {
        const savedFilter = localStorage.getItem('timeFilter');
        return savedFilter || 'all';
    });
    const [loadingStates, setLoadingStates] = useState({});
    const [playingStates, setPlayingStates] = useState({});
    const [pausedStates, setPausedStates] = useState({});
    const [progressStates, setProgressStates] = useState({});
    const [durationStates, setDurationStates] = useState({});
    const [currentTimeStates, setCurrentTimeStates] = useState({});
    const [currentlyPlaying, setCurrentlyPlaying] = useState(null);
    const audioRefs = useRef({});
    const eventHandlersRef = useRef({});
    const audioElements = useRef({});
    const api = useApi();

    // Update localStorage whenever timeFilter changes
    useEffect(() => {
        localStorage.setItem('timeFilter', timeFilter);
    }, [timeFilter]);

    // Define event handlers using useCallback to prevent recreation on each render
    const handleLoadedData = useCallback((id) => {
        console.log('Audio loaded successfully');
        if (audioRefs.current[id]) {
            const audio = audioRefs.current[id];
            // Only set duration if it's a valid number
            if (isFinite(audio.duration) && audio.duration > 0) {
                // Update with actual duration once it's available
                setDurationStates(prev => ({...prev, [id]: audio.duration}));
                // Don't reset progress here to avoid jumping
            } else {
                console.error('Invalid audio duration:', audio.duration);
                // Don't show error here as we already have an estimated duration
            }
        }
    }, []);

    const handleEnded = useCallback((id) => {
        console.log('Audio playback ended');
        cleanupAudio(id);
    }, []);

    const handleError = useCallback((id, e) => {
        console.error('Audio playback error:', e);
        // Don't throw the error, just log it and show a user-friendly message
        setError(`Failed to play audio for transcription ${id}. The audio file may be corrupted.`);
        cleanupAudio(id);
    }, []);

    const handleTimeUpdate = useCallback((id) => {
        if (audioRefs.current[id]) {
            const audio = audioRefs.current[id];
            // Ensure we have valid numbers before calculating progress
            if (isFinite(audio.currentTime)) {
                // Use actual duration if available, otherwise use estimated
                const duration = audio.duration && isFinite(audio.duration) && audio.duration > 0 
                    ? audio.duration 
                    : durationStates[id] || 0;
                    
                if (duration > 0) {
                    const progress = (audio.currentTime / duration) * 100;
                    setProgressStates(prev => ({...prev, [id]: progress}));
                    setCurrentTimeStates(prev => ({...prev, [id]: audio.currentTime}));
                }
            }
        }
    }, [durationStates]);

    // Define a cleanup function that can be used throughout the component
    const cleanupAudio = useCallback((id) => {
        if (audioRefs.current[id]) {
            const audio = audioRefs.current[id];
            
            // Remove event listeners using the stored handlers
            if (eventHandlersRef.current[id]) {
                const { loadedData, ended, error, timeUpdate } = eventHandlersRef.current[id];
                audio.removeEventListener('loadeddata', loadedData);
                audio.removeEventListener('ended', ended);
                audio.removeEventListener('error', error);
                audio.removeEventListener('timeupdate', timeUpdate);
            }
            
            // Update UI to show not playing
            setTranscriptions(prev => 
                prev.map(t => t.id === id ? {...t, isPlaying: false} : t)
            );
            setPlayingStates(prev => ({...prev, [id]: false}));
            setPausedStates(prev => ({...prev, [id]: false}));
        }
    }, []);

    const setupAudioElement = useCallback((audio, id) => {
        // Create bound event handlers for this specific audio element
        const boundLoadedData = () => handleLoadedData(id);
        const boundEnded = () => handleEnded(id);
        const boundError = (e) => handleError(id, e);
        const boundTimeUpdate = () => handleTimeUpdate(id);
        
        // Store the bound handlers for later cleanup
        eventHandlersRef.current[id] = {
            loadedData: boundLoadedData,
            ended: boundEnded,
            error: boundError,
            timeUpdate: boundTimeUpdate
        };
        
        // Add event listeners
        audio.addEventListener('loadeddata', boundLoadedData);
        audio.addEventListener('ended', boundEnded);
        audio.addEventListener('error', boundError);
        audio.addEventListener('timeupdate', boundTimeUpdate);
    }, [handleLoadedData, handleEnded, handleError, handleTimeUpdate]);

    const fetchTranscriptions = async () => {
        console.log('Starting fetchTranscriptions, authToken:', authToken ? 'exists' : 'missing');
        if (!authToken) {
            console.log('No authToken found, setting error');
            setError('Not authenticated. Please log in.');
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            console.log('Making API request...');
            const response = await fetch(`${API_URL}/api/transcriptions?page=${currentPage}&per_page=${perPage}&time_filter=${timeFilter}`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Accept': 'application/json'
                }
            });
            
            console.log('Response status:', response.status);
            if (!response.ok) {
                if (response.status === 401) {
                    console.log('401 Unauthorized, handling session expired');
                    handleSessionExpired();
                    return;
                }
                const errorText = await response.text();
                console.log('Error response:', errorText);
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.message || 'Failed to fetch transcriptions');
                } catch (e) {
                    throw new Error(errorText || 'Failed to fetch transcriptions');
                }
            }
            
            const data = await response.json();
            console.log('Received data:', data);
            setTranscriptions(data.items);
            setTotalPages(data.total_pages);
            setHasMore(data.has_more);
        } catch (err) {
            console.error('Error in fetchTranscriptions:', err);
            setError(err.message || 'Failed to fetch transcriptions');
        } finally {
            console.log('Setting isLoading to false');
            setIsLoading(false);
        }
    };

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            setCurrentPage(newPage);
        }
    };

    const handlePerPageChange = (event) => {
        const newPerPage = parseInt(event.target.value);
        setPerPage(newPerPage);
        setCurrentPage(1); // Reset to first page when changing items per page
    };

    const handleTimeFilterChange = (e) => {
        const newFilter = e.target.value;
        setTimeFilter(newFilter);
        // Reset pagination when filter changes
        setCurrentPage(1);
        setHasMore(true);
        // Clear existing transcriptions
        setTranscriptions([]);
    };

    useEffect(() => {
        console.log('useEffect triggered, dependencies:', { currentPage, perPage, timeFilter, authToken });
        fetchTranscriptions();
    }, [currentPage, perPage, timeFilter, authToken]);

    const handleSelectAll = (e) => {
        if (e.target.checked) {
            setSelectedIds(transcriptions.map(t => t.id));
        } else {
            setSelectedIds([]);
        }
    };

    const handleSelect = (id) => {
        setSelectedIds(prev => {
            if (prev.includes(id)) {
                return prev.filter(i => i !== id);
            } else {
                return [...prev, id];
            }
        });
    };

    const handleDelete = async (id) => {
        try {
            const response = await api.delete(`/api/transcriptions/${id}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            setTranscriptions(transcriptions.filter(t => t.id !== id));
        } catch (err) {
            console.error('Error deleting transcription:', err);
            if (err.message.includes('Session expired')) {
                handleSessionExpired();
            } else {
                setError('Failed to delete transcription. Please try again.');
            }
        }
    };

    const handleDeleteSelected = async () => {
        if (selectedIds.length === 0) return;
        
        try {
            const response = await api.delete('/api/transcriptions', {
                body: JSON.stringify({ ids: selectedIds })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            setTranscriptions(transcriptions.filter(t => !selectedIds.includes(t.id)));
            setSelectedIds([]);
        } catch (err) {
            console.error('Error deleting selected transcriptions:', err);
            if (err.message.includes('Session expired')) {
                handleSessionExpired();
            } else {
                setError('Failed to delete selected transcriptions. Please try again.');
            }
        }
    };

    const handlePlay = async (id) => {
        try {
            // Show loading state for this specific transcription
            setLoadingStates(prev => ({...prev, [id]: true}));
            
            // If we already have an audio element for this ID, use it
            if (audioRefs.current[id]) {
                const audio = audioRefs.current[id];
                
                // If it was paused, just resume
                if (pausedStates[id]) {
                    try {
                        // For iOS, we need to handle the play promise
                        const playPromise = audio.play();
                        if (playPromise !== undefined) {
                            playPromise
                                .then(() => {
                                    setPausedStates(prev => ({...prev, [id]: false}));
                                    setPlayingStates(prev => ({...prev, [id]: true}));
                                    setLoadingStates(prev => ({...prev, [id]: false}));
                                })
                                .catch(error => {
                                    console.error('Error resuming audio:', error);
                                    // If resume fails, try to reload the audio
                                    audio.src = audio.src;
                                    const retryPromise = audio.play();
                                    if (retryPromise !== undefined) {
                                        retryPromise
                                            .then(() => {
                                                setPausedStates(prev => ({...prev, [id]: false}));
                                                setPlayingStates(prev => ({...prev, [id]: true}));
                                                setLoadingStates(prev => ({...prev, [id]: false}));
                                            })
                                            .catch(retryError => {
                                                console.error('Error retrying audio playback:', retryError);
                                                setError(`Failed to play audio for transcription ${id}. Please try again.`);
                                                cleanupAudio(id);
                                            });
                                    }
                                });
                        }
                        return;
                    } catch (playError) {
                        console.error('Error resuming audio:', playError);
                        // If resume fails, try to reload the audio
                        audio.src = audio.src;
                        await audio.play();
                    }
                }

                // Otherwise, we need to set up the audio element
                setupAudioElement(audio, id);
            } else {
                // Create a new audio element
                const audio = new Audio();
                audioRefs.current[id] = audio;
                
                // Set up the audio element
                setupAudioElement(audio, id);
            }
            
            // Fetch the audio data with proper authorization
            const response = await api.get(`/api/transcriptions/${id}/audio`, {
                headers: {
                    'Accept': 'audio/*'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Get the content length header to estimate duration
            const contentLength = response.headers.get('Content-Length');
            if (contentLength) {
                // Estimate duration based on file size
                // AAC typically has a bitrate of around 128 kbps
                const fileSizeBytes = parseInt(contentLength, 10);
                const estimatedDurationSeconds = (fileSizeBytes * 8) / (128 * 1024); // Convert to seconds
                
                // Set the estimated duration
                setDurationStates(prev => ({...prev, [id]: estimatedDurationSeconds}));
                setProgressStates(prev => ({...prev, [id]: 0}));
                setCurrentTimeStates(prev => ({...prev, [id]: 0}));
            }
            
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);

            // Set the source to the blob URL
            audioRefs.current[id].src = audioUrl;

            // For iOS, we need to load the audio first
            audioRefs.current[id].load();
            
            // Play the audio
            try {
                // For iOS, we need to play in response to a user gesture
                const playPromise = audioRefs.current[id].play();
                if (playPromise !== undefined) {
                    playPromise
                        .then(() => {
                            setPlayingStates(prev => ({...prev, [id]: true}));
                            setPausedStates(prev => ({...prev, [id]: false}));
                            setLoadingStates(prev => ({...prev, [id]: false}));
                        })
                        .catch(error => {
                            console.error('Error playing audio:', error);
                            // For iOS, we might need to try a different approach
                            if (error.name === 'NotAllowedError' || error.name === 'AbortError') {
                                // Try to play without user interaction (might work on some iOS versions)
                                audioRefs.current[id].play().catch(e => {
                                    console.error('Second attempt failed:', e);
                                    setError(`Failed to play audio for transcription ${id}. Please try again.`);
                                    cleanupAudio(id);
                                });
                            } else {
                                setError(`Failed to play audio for transcription ${id}. Please try again.`);
                                cleanupAudio(id);
                            }
                        });
                }
            } catch (playError) {
                console.error('Error playing audio:', playError);
                setError(`Failed to play audio for transcription ${id}. The audio file may be corrupted.`);
                cleanupAudio(id);
            }
        } catch (err) {
            console.error('Error playing audio:', err);
            if (err.message.includes('Session expired')) {
                handleSessionExpired();
            } else {
                setError(`Failed to play audio for transcription ${id}. Please try again.`);
            }
            setLoadingStates(prev => ({...prev, [id]: false}));
        }
    };
    
    const handlePause = (id) => {
        if (audioRefs.current[id]) {
            audioRefs.current[id].pause();
            setPausedStates(prev => ({...prev, [id]: true}));
            setPlayingStates(prev => ({...prev, [id]: false}));
        }
    };
    
    const handleStop = (id) => {
        if (audioRefs.current[id]) {
            audioRefs.current[id].pause();
            audioRefs.current[id].currentTime = 0;
            setPausedStates(prev => ({...prev, [id]: false}));
            setPlayingStates(prev => ({...prev, [id]: false}));
            setProgressStates(prev => ({...prev, [id]: 0}));
            setCurrentTimeStates(prev => ({...prev, [id]: 0}));
        }
    };
    
    const handleProgressClick = (id, event) => {
        if (audioRefs.current[id]) {
            const progressBar = event.currentTarget;
            const rect = progressBar.getBoundingClientRect();
            const clickPosition = event.clientX - rect.left;
            const progressBarWidth = rect.width;
            const percentage = (clickPosition / progressBarWidth) * 100;
            
            // Ensure percentage is within valid range
            const validPercentage = Math.max(0, Math.min(100, percentage));
            
            // Use actual duration if available, otherwise use estimated
            const duration = audioRefs.current[id].duration && isFinite(audioRefs.current[id].duration) && audioRefs.current[id].duration > 0
                ? audioRefs.current[id].duration
                : durationStates[id] || 0;
                
            if (duration > 0) {
                // Calculate new time and ensure it's a valid number
                const newTime = (validPercentage / 100) * duration;
                
                // Only set currentTime if it's a valid finite number
                if (isFinite(newTime) && newTime >= 0 && newTime <= duration) {
                    audioRefs.current[id].currentTime = newTime;
                    
                    // Update the progress state
                    setProgressStates(prev => ({...prev, [id]: validPercentage}));
                    setCurrentTimeStates(prev => ({...prev, [id]: newTime}));
                }
            }
        }
    };

    const handleRefresh = () => {
        setCurrentPage(1);
        setTranscriptions([]);
        fetchTranscriptions();
    };

    const formatTime = (seconds) => {
        // Ensure seconds is a valid number
        if (!isFinite(seconds) || isNaN(seconds) || seconds < 0) return "0:00";
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    if (isLoading) {
        return <div className="loading">Loading transcriptions...</div>;
    }

    return (
        <div className="transcription-list">
            {error && (
                <div className="error-message">
                    {error}
                    <button 
                        className="dismiss-error" 
                        onClick={() => setError(null)}
                        title="Dismiss error"
                    >
                        ×
                    </button>
                </div>
            )}
            <div className="transcription-list-header">
                <div className="select-all-container">
                    <input
                        type="checkbox"
                        id="select-all"
                        checked={selectedIds.length === transcriptions.length && transcriptions.length > 0}
                        onChange={handleSelectAll}
                    />
                    <label htmlFor="select-all">Select All</label>
                </div>
                <div className="action-buttons">
                    <button 
                        className="refresh-button" 
                        onClick={handleRefresh}
                        title="Refresh list"
                    >
                        <FaSync /> Refresh
                    </button>
                    <button 
                        className="delete-selected-button" 
                        onClick={handleDeleteSelected}
                        disabled={selectedIds.length === 0}
                    >
                        <FaTrash /> Delete Selected
                    </button>
                </div>
            </div>
            <div className="time-filter-container">
                <label htmlFor="time-filter">Time period:</label>
                <select 
                    id="time-filter" 
                    value={timeFilter} 
                    onChange={handleTimeFilterChange}
                    className="time-filter-select"
                >
                    <option value="all">All time</option>
                    <option value="today">Last 24 hours</option>
                    <option value="week">Last 7 days</option>
                    <option value="month">Last 30 days</option>
                </select>
            </div>
            <div className="transcription-items">
                {transcriptions.map((transcription, index) => (
                    <div key={transcription.id} className="transcription-item">
                        <div className="transcription-content">
                            <div className="transcription-header">
                                <div className="record-meta">
                                    <span className="ordinal-number">#{((currentPage - 1) * perPage) + index + 1}</span>
                                    <span className="user-info">{transcription.username || 'N/A'} ({transcription.id})</span>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={selectedIds.includes(transcription.id)}
                                    onChange={() => handleSelect(transcription.id)}
                                    className="transcription-checkbox"
                                />
                                <p>{transcription.transcript}</p>
                            </div>
                            <div className="transcription-meta">
                                <span className="file-size">{transcription.file_size}</span>
                                <span className="created-at">
                                    {new Date(transcription.created_at).toLocaleString()}
                                </span>
                                <span className={`client-type ${transcription.client_type?.toLowerCase()}`}>
                                    {transcription.client_type || 'Unknown Device'}
                                </span>
                            </div>
                        </div>
                        <div className="audio-controls">
                            {playingStates[transcription.id] && !pausedStates[transcription.id] ? (
                                <button 
                                    className="pause-button" 
                                    onClick={() => handlePause(transcription.id)}
                                    title="Pause audio"
                                >
                                    <FaPause />
                                </button>
                            ) : (
                                <button 
                                    className="play-button" 
                                    onClick={() => handlePlay(transcription.id)}
                                    title="Play audio"
                                    disabled={loadingStates[transcription.id]}
                                >
                                    {loadingStates[transcription.id] ? 'Loading...' : <FaPlay />}
                                </button>
                            )}
                            <button 
                                className="stop-button" 
                                onClick={() => handleStop(transcription.id)}
                                title="Stop audio"
                                disabled={!playingStates[transcription.id] && !pausedStates[transcription.id]}
                            >
                                <FaStop />
                            </button>
                            <div className="progress-container">
                                <div 
                                    className="progress-bar-container"
                                    onClick={(e) => handleProgressClick(transcription.id, e)}
                                >
                                    <div 
                                        className="progress-bar" 
                                        style={{width: `${progressStates[transcription.id] || 0}%`}}
                                    ></div>
                                </div>
                                <div className="time-display">
                                    <span>{formatTime(currentTimeStates[transcription.id] || 0)}</span>
                                    <span>/</span>
                                    <span>{formatTime(durationStates[transcription.id] || 0)}</span>
                                </div>
                            </div>
                        </div>
                        <button 
                            className="delete-button" 
                            onClick={() => handleDelete(transcription.id)}
                            title="Delete transcription"
                        >
                            <FaTrash />
                        </button>
                    </div>
                ))}
            </div>
            <div className="pagination-container">
                <div className="pagination">
                    <button 
                        className="pagination-button"
                        onClick={() => handlePageChange(1)}
                        disabled={currentPage === 1}
                    >
                        <FaAngleDoubleLeft />
                    </button>
                    <button 
                        className="pagination-button"
                        onClick={() => handlePageChange(currentPage - 1)}
                        disabled={currentPage === 1}
                    >
                        <FaAngleLeft />
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1)
                        .filter(page => {
                            if (totalPages <= 5) return true;
                            if (page === 1 || page === totalPages) return true;
                            if (Math.abs(page - currentPage) <= 1) return true;
                            return false;
                        })
                        .map((page, index, array) => {
                            if (index > 0 && array[index - 1] !== page - 1) {
                                return (
                                    <React.Fragment key={`ellipsis-${page}`}>
                                        <span className="pagination-ellipsis">...</span>
                                        <button
                                            className={`pagination-button ${currentPage === page ? 'active' : ''}`}
                                            onClick={() => handlePageChange(page)}
                                        >
                                            {page}
                                        </button>
                                    </React.Fragment>
                                );
                            }
                            return (
                                <button
                                    key={page}
                                    className={`pagination-button ${currentPage === page ? 'active' : ''}`}
                                    onClick={() => handlePageChange(page)}
                                >
                                    {page}
                                </button>
                            );
                        })}
                    <button 
                        className="pagination-button"
                        onClick={() => handlePageChange(currentPage + 1)}
                        disabled={currentPage === totalPages}
                    >
                        <FaAngleRight />
                    </button>
                    <button 
                        className="pagination-button"
                        onClick={() => handlePageChange(totalPages)}
                        disabled={currentPage === totalPages}
                    >
                        <FaAngleDoubleRight />
                    </button>
                </div>
                <div className="per-page-selector">
                    <label htmlFor="per-page">Results per page:</label>
                    <select 
                        id="per-page" 
                        value={perPage} 
                        onChange={handlePerPageChange}
                    >
                        <option value="5">5</option>
                        <option value="10">10</option>
                        <option value="20">20</option>
                        <option value="50">50</option>
                    </select>
                </div>
            </div>
        </div>
    );
};

export default TranscriptionList; 