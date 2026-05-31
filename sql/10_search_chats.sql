-- 10_search_chats.sql
-- Function to search chat sessions by title or message content with pagination

CREATE OR REPLACE FUNCTION search_chat_sessions(
    p_user_id UUID, 
    p_query TEXT, 
    p_limit INT, 
    p_offset INT
)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.user_id, s.title, s.created_at, s.updated_at
    FROM chat_sessions s
    WHERE s.user_id = p_user_id
      AND (
        s.title ILIKE '%' || p_query || '%'
        OR EXISTS (
            SELECT 1 FROM chat_messages m
            WHERE m.session_id = s.id
              AND m.content ILIKE '%' || p_query || '%'
        )
      )
    ORDER BY s.updated_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;
