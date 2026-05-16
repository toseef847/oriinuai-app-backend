-- Add file_hash column to books table to prevent duplicate uploads
ALTER TABLE public.books ADD COLUMN IF NOT EXISTS file_hash TEXT UNIQUE;
