import pytest
from fastapi import status
from sqlalchemy import select

from app.models.user import users
from app.models.transcription import transcription_chunks

@pytest.mark.asyncio
async def test_login_success(client, test_user):
    """Test successful login."""
    response = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testuser"
    assert data["user"]["role"] == "user"

@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    """Test login with wrong password."""
    response = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "wrongpass"
    })
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Test login with nonexistent user."""
    response = await client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "testpass123"
    })
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_reset_password_success(client, test_user):
    """Test successful password reset."""
    response = await client.post("/api/auth/reset-password", json={
        "username": "testuser",
        "current_password": "testpass123",
        "new_password": "newpass123"
    })
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Password reset successful"
    
    # Verify the password was changed
    response = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "newpass123"
    })
    
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_reset_password_wrong_current_password(client, test_user):
    """Test password reset with wrong current password."""
    response = await client.post("/api/auth/reset-password", json={
        "username": "testuser",
        "current_password": "wrongpass",
        "new_password": "newpass123"
    })
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect current password"

@pytest.mark.asyncio
async def test_get_transcriptions_empty(client, test_user_token):
    """Test getting transcriptions with empty database."""
    response = await client.get(
        "/api/transcriptions",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["has_more"] is False

@pytest.mark.asyncio
async def test_get_transcriptions_with_data(client, test_user_token, db_session):
    """Test getting transcriptions with data in the database."""
    # Insert test data
    test_data = [
        {
            "session_id": "test-session-1",
            "audio_chunk": b"test audio data 1",
            "transcript": "Test transcription 1"
        },
        {
            "session_id": "test-session-2",
            "audio_chunk": b"test audio data 2",
            "transcript": "Test transcription 2"
        }
    ]
    
    for data in test_data:
        query = transcription_chunks.insert().values(**data)
        await db_session.execute(query)
    
    await db_session.commit()
    
    # Get transcriptions
    response = await client.get(
        "/api/transcriptions",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["has_more"] is False
    
    # Verify the items
    for i, item in enumerate(data["items"]):
        assert item["session_id"] == f"test-session-{i+1}"
        assert item["transcript"] == f"Test transcription {i+1}"
        assert "file_size" in item

@pytest.mark.asyncio
async def test_get_transcriptions_unauthorized(client):
    """Test getting transcriptions without authentication."""
    response = await client.get("/api/transcriptions")
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_delete_transcription_success(client, test_user_token, db_session):
    """Test successful transcription deletion."""
    # Insert test data
    test_data = {
        "session_id": "test-session",
        "audio_chunk": b"test audio data",
        "transcript": "Test transcription"
    }
    
    query = transcription_chunks.insert().values(**test_data)
    result = await db_session.execute(query)
    await db_session.commit()
    
    # Get the inserted ID
    query = select(transcription_chunks).where(transcription_chunks.c.session_id == "test-session")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    transcription_id = transcription.id
    
    # Delete the transcription
    response = await client.delete(
        f"/api/transcriptions/{transcription_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Transcription deleted successfully"
    
    # Verify the transcription was deleted
    query = select(transcription_chunks).where(transcription_chunks.c.id == transcription_id)
    result = await db_session.execute(query)
    transcription = result.fetchone()
    
    assert transcription is None

@pytest.mark.asyncio
async def test_delete_transcription_nonexistent(client, test_user_token):
    """Test deletion of nonexistent transcription."""
    response = await client.delete(
        "/api/transcriptions/999",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Transcription not found"

@pytest.mark.asyncio
async def test_delete_multiple_transcriptions_success(client, test_user_token, db_session):
    """Test successful deletion of multiple transcriptions."""
    # Insert test data
    test_data = [
        {
            "session_id": "test-session-1",
            "audio_chunk": b"test audio data 1",
            "transcript": "Test transcription 1"
        },
        {
            "session_id": "test-session-2",
            "audio_chunk": b"test audio data 2",
            "transcript": "Test transcription 2"
        },
        {
            "session_id": "test-session-3",
            "audio_chunk": b"test audio data 3",
            "transcript": "Test transcription 3"
        }
    ]
    
    for data in test_data:
        query = transcription_chunks.insert().values(**data)
        await db_session.execute(query)
    
    await db_session.commit()
    
    # Get the inserted IDs
    query = select(transcription_chunks).where(transcription_chunks.c.session_id.in_(["test-session-1", "test-session-2"]))
    result = await db_session.execute(query)
    transcriptions = result.fetchall()
    transcription_ids = [t.id for t in transcriptions]
    
    # Delete the transcriptions
    response = await client.post(
        "/api/transcriptions/delete-multiple",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={"ids": transcription_ids}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Transcriptions deleted successfully"
    
    # Verify the transcriptions were deleted
    query = select(transcription_chunks).where(transcription_chunks.c.id.in_(transcription_ids))
    result = await db_session.execute(query)
    transcriptions = result.fetchall()
    
    assert len(transcriptions) == 0
    
    # Verify the remaining transcription
    query = select(transcription_chunks).where(transcription_chunks.c.session_id == "test-session-3")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    
    assert transcription is not None

@pytest.mark.asyncio
async def test_delete_multiple_transcriptions_empty(client, test_user_token):
    """Test deletion of multiple transcriptions with empty list."""
    response = await client.post(
        "/api/transcriptions/delete-multiple",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={"ids": []}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "No transcription IDs provided"

@pytest.mark.asyncio
async def test_get_transcription_audio_success(client, test_user_token, db_session):
    """Test successful retrieval of transcription audio."""
    # Insert test data
    test_data = {
        "session_id": "test-session",
        "audio_chunk": b"test audio data",
        "transcript": "Test transcription"
    }
    
    query = transcription_chunks.insert().values(**test_data)
    result = await db_session.execute(query)
    await db_session.commit()
    
    # Get the inserted ID
    query = select(transcription_chunks).where(transcription_chunks.c.session_id == "test-session")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    transcription_id = transcription.id
    
    # Get the audio
    response = await client.get(
        f"/api/transcriptions/{transcription_id}/audio",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"test audio data"

@pytest.mark.asyncio
async def test_get_transcription_audio_nonexistent(client, test_user_token):
    """Test retrieval of audio for nonexistent transcription."""
    response = await client.get(
        "/api/transcriptions/999/audio",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Transcription not found" 