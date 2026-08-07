# ====================================
#  🔰 [RESEARCH AGENT] Retriever
# ====================================

import pickle
import re
from pathlib import Path

from langchain_classic.retrievers import (
    ContextualCompressionRetriever,
    EnsembleRetriever,
)
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from config import Settings
from ingest import CHUNKS_FILENAME

settings = Settings()

RERANKER_MODEL = "BAAI/bge-reranker-base"
BM25_WEIGHT = 0.4
VECTOR_WEIGHT = 0.6


def _tokenize(text: str) -> list[str]:
    """Lowercase + strip punctuation, so 'seq2seq', 'Seq2seq' and 'seq2seq,'
    all become the same BM25 token."""
    return re.findall(r"\w+", text.lower())


def get_retriever():
    index_dir = Path(settings.index_dir)
    if not (index_dir / "index.faiss").exists():
        raise FileNotFoundError(
            f"No index in {index_dir}/. Run `python ingest.py` first."
        )

    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model, api_key=settings.api_key
    )

    vectorstore = FAISS.load_local(
        str(index_dir), embeddings, allow_dangerous_deserialization=True
    )

    chunks_path = index_dir / CHUNKS_FILENAME
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"{chunks_path} missing (found index.faiss but not chunks.pkl). "
            "Re-run `python ingest.py`."
        )
    try:
        with chunks_path.open("rb") as f:
            chunks = pickle.load(f)
    except (pickle.UnpicklingError, EOFError) as e:
        raise RuntimeError(
            f"{chunks_path} is corrupt — re-run `python ingest.py`: {e}"
        ) from e

    bm25_retriever = BM25Retriever.from_documents(chunks, preprocess_func=_tokenize)
    bm25_retriever.k = settings.retrieval_top_k

    hybrid_retriever = EnsembleRetriever(
        retrievers=[
            bm25_retriever,
            vectorstore.as_retriever(search_kwargs={"k": settings.retrieval_top_k}),
        ],
        weights=[BM25_WEIGHT, VECTOR_WEIGHT],
    )

    reranker = HuggingFaceCrossEncoder(model_name=RERANKER_MODEL)
    return ContextualCompressionRetriever(
        base_compressor=CrossEncoderReranker(
            model=reranker, top_n=settings.rerank_top_n
        ),
        base_retriever=hybrid_retriever,
    )
