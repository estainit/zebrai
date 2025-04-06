import React, { useState, useEffect } from 'react';
import './TranscriptionList.css';
import { FaPlay, FaTrash, FaSync } from 'react-icons/fa';

const TranscriptionList = ({ credentials }) => {
    const [transcriptions, setTranscriptions] = useState([]);
    const [selectedIds, setSelectedIds] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasMore, setHasMore] = useState(true);
    const perPage = 10;

    const fetchTranscriptions = async () => {
        try {
            setIsLoading(true);
            const response = await fetch(
                `/api/transcriptions?page=${currentPage}&per_page=${perPage}`,
                {
                    headers: {
                        'Authorization': `Bearer ${credentials}`,
                        'Accept': 'application/json'
                    }
                }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            // Create a Map to ensure unique entries by ID
            const uniqueTranscriptions = new Map();
            
            // Add existing transcriptions to the map
            transcriptions.forEach(t => uniqueTranscriptions.set(t.id, t));
            
            // Add new transcriptions to the map
            data.items.forEach(t => uniqueTranscriptions.set(t.id, t));
            
            // Convert map values back to array
            setTranscriptions(Array.from(uniqueTranscriptions.values()));
            setTotalPages(Math.ceil(data.total / perPage));
            setHasMore(data.has_more);
            setError(null);
        } catch (err) {
            console.error('Error fetching transcriptions:', err);
            setError('Failed to load transcriptions');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchTranscriptions();
    }, [currentPage, credentials]);

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
            const response = await fetch(`/api/transcriptions/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${credentials}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            setTranscriptions(transcriptions.filter(t => t.id !== id));
        } catch (err) {
            console.error('Error deleting transcription:', err);
            setError('Failed to delete transcription. Please try again.');
        }
    };

    const handleDeleteSelected = async () => {
        if (selectedIds.length === 0) return;
        
        try {
            const response = await fetch('/api/transcriptions', {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${credentials}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ids: selectedIds })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            setTranscriptions(transcriptions.filter(t => !selectedIds.includes(t.id)));
            setSelectedIds([]);
        } catch (err) {
            console.error('Error deleting selected transcriptions:', err);
            setError('Failed to delete selected transcriptions. Please try again.');
        }
    };

    const handlePlay = async (id) => {
        try {
            // Show loading state for this specific transcription
            setTranscriptions(prev => 
                prev.map(t => t.id === id ? {...t, isPlaying: true} : t)
            );
            
            // Create a new audio element
            const audio = new Audio();
            
            // Set up event listeners
            const cleanup = () => {
                audio.removeEventListener('ended', handleEnded);
                audio.removeEventListener('error', handleError);
                audio.removeEventListener('loadeddata', handleLoadedData);
                
                // Update UI to show not playing
                setTranscriptions(prev => 
                    prev.map(t => t.id === id ? {...t, isPlaying: false} : t)
                );
            };
            
            const handleLoadedData = () => {
                console.log('Audio loaded successfully');
            };
            
            const handleEnded = () => {
                console.log('Audio playback ended');
                cleanup();
            };
            
            const handleError = (e) => {
                console.error('Audio playback error:', e);
                // Don't throw the error, just log it and show a user-friendly message
                setError(`Failed to play audio for transcription ${id}. The audio file may be corrupted.`);
                cleanup();
            };
            
            // Add event listeners
            audio.addEventListener('ended', handleEnded);
            audio.addEventListener('error', handleError);
            audio.addEventListener('loadeddata', handleLoadedData);
            
            // Fetch the audio data with proper authorization
            const response = await fetch(`/api/transcriptions/${id}/audio`, {
                headers: {
                    'Authorization': `Bearer ${credentials}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // Set the source to the blob URL
            audio.src = audioUrl;
            
            // Play the audio
            try {
                await audio.play();
            } catch (playError) {
                console.error('Error playing audio:', playError);
                setError(`Failed to play audio for transcription ${id}. The audio file may be corrupted.`);
                cleanup();
            }
        } catch (err) {
            console.error('Error playing audio:', err);
            setError(`Failed to play audio for transcription ${id}. Please try again.`);
            
            // Reset playing state
            setTranscriptions(prev => 
                prev.map(t => t.id === id ? {...t, isPlaying: false} : t)
            );
        }
    };

    const loadMore = () => {
        if (!isLoading && hasMore) {
            setCurrentPage(prev => prev + 1);
        }
    };

    const handleRefresh = () => {
        setCurrentPage(1);
        setTranscriptions([]);
        fetchTranscriptions();
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
            <table className="transcription-table">
                <thead>
                    <tr>
                        <th>Select</th>
                        <th>ID</th>
                        <th>Transcript</th>
                        <th>Size</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {transcriptions.map((transcription) => (
                        <tr key={transcription.id}>
                            <td>
                                <input
                                    type="checkbox"
                                    checked={selectedIds.includes(transcription.id)}
                                    onChange={() => handleSelect(transcription.id)}
                                />
                            </td>
                            <td>{transcription.id}</td>
                            <td>{transcription.transcript || 'No transcript available'}</td>
                            <td>{transcription.file_size || '0 B'}</td>
                            <td>
                                <button 
                                    className="play-button" 
                                    onClick={() => handlePlay(transcription.id)}
                                    title="Play audio"
                                    disabled={transcription.isPlaying}
                                >
                                    {transcription.isPlaying ? 'Playing...' : <FaPlay />}
                                </button>
                                <button 
                                    className="delete-button" 
                                    onClick={() => handleDelete(transcription.id)}
                                    title="Delete transcription"
                                >
                                    <FaTrash />
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {hasMore && (
                <div className="load-more-container">
                    <button 
                        className="load-more-button" 
                        onClick={loadMore}
                        disabled={isLoading}
                    >
                        {isLoading ? 'Loading...' : 'Load More'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default TranscriptionList; 