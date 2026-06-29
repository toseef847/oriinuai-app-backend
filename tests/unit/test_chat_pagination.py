import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.core.security import get_current_user_id, get_user_db

client = TestClient(app)

# Mock user_id
MOCK_USER_ID = "test-user-id"


@pytest.fixture
def mock_user_id():
    app.dependency_overrides[get_current_user_id] = lambda: MOCK_USER_ID
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_list_chats_pagination(mock_user_id):
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_order = MagicMock()
    mock_range = MagicMock()
    mock_execute = AsyncMock()

    # Mock return data
    mock_data = [{"id": "chat1", "title": "Test Chat 1"}]
    mock_execute.return_value.data = mock_data

    # Chain mocks
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.order.return_value = mock_order
    mock_order.range.return_value = mock_range
    mock_range.execute = mock_execute

    app.dependency_overrides[get_user_db] = lambda: mock_supabase
    try:
        response = client.get("/api/v1/chats?page=1&page_size=1")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["items"] == mock_data
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert data["has_more"] is True  # len(mock_data) == 1 (page_size)

        # Verify calls
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("user_id", MOCK_USER_ID)
        mock_eq.order.assert_called_once_with("updated_at", desc=True)
        mock_order.range.assert_called_once_with(0, 0)  # start=(1-1)*1, end=0+1-1
    finally:
        app.dependency_overrides.pop(get_user_db, None)


@pytest.mark.asyncio
async def test_search_chats_rpc_call(mock_user_id):
    mock_supabase = MagicMock()
    mock_rpc = MagicMock()
    mock_execute = AsyncMock()

    mock_data = [{"id": "chat1", "title": "Matched Chat"}]
    mock_execute.return_value.data = mock_data

    mock_supabase.rpc.return_value = mock_rpc
    mock_rpc.execute = mock_execute

    app.dependency_overrides[get_user_db] = lambda: mock_supabase
    try:
        response = client.get("/api/v1/chats/search?q=test&page=2&page_size=5")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["items"] == mock_data
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert data["has_more"] is False  # len(mock_data) == 1, page_size == 5

        # Verify RPC call
        mock_supabase.rpc.assert_called_once_with(
            "search_chat_sessions",
            {
                "p_user_id": MOCK_USER_ID,
                "p_query": "test",
                "p_limit": 5,
                "p_offset": 5,  # (2-1)*5
            },
        )
    finally:
        app.dependency_overrides.pop(get_user_db, None)
