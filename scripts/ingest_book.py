import argparse
from pathlib import Path
from app.services.rag.chunker import chunk_by_day
from app.utils.pdf_extractor import extract_text_from_pdf


def main():
    parser = argparse.ArgumentParser(description="Dry-run ingest for 365 African Proverbs PDF.")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF file.")
    args = parser.parse_args()

    file_bytes = args.pdf_path.read_bytes()
    text = extract_text_from_pdf(file_bytes)
    chunks = chunk_by_day(text)
    print(f"Found {len(chunks)} day chunks.")
    if chunks:
        first = chunks[0]
        print("Day 1 law name:", first["law_name"])
        print("Preview:", first["content"][:500].replace('\n', ' '))


if __name__ == "__main__":
    main()
