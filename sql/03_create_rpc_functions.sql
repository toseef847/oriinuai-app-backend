-- RAG similarity search
create or replace function match_chunks(
    query_embedding vector(768),
    match_count     int,
    filter_book_id  uuid default null
)
returns table (
    id          uuid,
    content     text,
    similarity  float,
    metadata    jsonb,
    chunk_index int
)
language plpgsql as $$
begin
    return query
    select
        bc.id,
        bc.content,
        1 - (bc.embedding <=> query_embedding) as similarity,
        bc.metadata,
        bc.chunk_index
    from public.book_chunks bc
    where
        (filter_book_id is null or bc.book_id = filter_book_id)
        and bc.embedding is not null
    order by bc.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- Increment daily usage
create or replace function increment_usage(
    p_user_id uuid,
    p_tokens  int default 0
)
returns void language plpgsql as $$
begin
    insert into public.usage_logs (user_id, date, messages_count, tokens_used)
    values (p_user_id, current_date, 1, p_tokens)
    on conflict (user_id, date)
    do update set
        messages_count = usage_logs.messages_count + 1,
        tokens_used    = usage_logs.tokens_used + p_tokens;
end;
$$;
