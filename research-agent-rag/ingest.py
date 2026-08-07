# ====================================
#  🔰 [RESEARCH AGENT] Ingest
# ====================================

import os
import pickle
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Settings

settings = Settings()

CHUNKS_FILENAME = "chunks.pkl"


def load_documents(data_dir: Path) -> list:
    """One Document per PDF page; skips unreadable files instead of aborting the batch."""
    documents = []
    for path in sorted(data_dir.glob("*.pdf")):
        try:
            pages = PyPDFLoader(str(path)).load()
        except Exception as e:  # noqa: BLE001 - PDF parsing failures vary
            print(f"  ⚠️  Skipping {path.name}: {type(e).__name__}: {e}")
            continue

        # scanned/image-only PDFs load with empty pages and vanish silently otherwise
        chars = sum(len(p.page_content) for p in pages)
        if chars == 0:
            print(
                f"  ⚠️  {path.name}: {len(pages)} pages, no extractable text (scanned?)"
            )
        else:
            print(f"  {path.name}: {len(pages)} pages, {chars} characters")

        documents.extend(pages)
    return documents


def ingest() -> None:
    data_dir = Path(settings.data_dir)
    index_dir = Path(settings.index_dir)

    print(f"Loading PDFs from {data_dir}/...")
    documents = load_documents(data_dir)
    if not documents:
        print(f"No PDFs found in {data_dir}/. Nothing to index.")
        return
    print(f"  {len(documents)} pages loaded total")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    print(f"  {len(chunks)} chunks created")

    print(f"Embedding {len(chunks)} chunks with {settings.embedding_model}...")
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model, api_key=settings.api_key
    )
    vectorstore = FAISS.from_documents(chunks, embeddings)

    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    print(f"FAISS index saved to {index_dir}/")

    # BM25 needs raw chunk text; write via tmp+replace so a failure mid-write
    # can't leave chunks.pkl truncated
    chunks_path = index_dir / CHUNKS_FILENAME
    tmp_path = chunks_path.with_suffix(".tmp")
    with tmp_path.open("wb") as f:
        pickle.dump(chunks, f)
    os.replace(tmp_path, chunks_path)
    print(f"Chunks saved to {chunks_path} (for BM25)")


if __name__ == "__main__":
    ingest()
