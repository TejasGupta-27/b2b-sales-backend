# vectorstore_ingestor.py

import os
import re
from uuid import uuid4
from typing import List, Optional
from langchain_community.embeddings.azure_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from pydantic import model_validator
import web_scraper

CHROMA_DIR = "./chroma_store"

class FixedAzureOpenAIEmbeddings(AzureOpenAIEmbeddings):
    @model_validator(mode="before")
    def add_default_validate_base_url(cls, values):
        if "validate_base_url" not in values:
            values["validate_base_url"] = True
        return values

# Azure config
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AZURE_API_VERSION = "2025-01-01-preview"

def get_embedder():
    return FixedAzureOpenAIEmbeddings(
        deployment=AZURE_EMBEDDING_DEPLOYMENT,
        openai_api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        openai_api_version=AZURE_API_VERSION,
        chunk_size=1024,
    )

def parse_products(raw_text: str) -> List[str]:
    """Split raw scraped text into product blocks."""
    products = raw_text.strip().split("\n\n")
    return [p.strip() for p in products if len(p.strip()) > 30]

def extract_metadata(chunk: str, search_query: str) -> dict:
    brand = re.search(r"Brand: (.+)", chunk)
    ptype = re.search(r"Type: (.+)", chunk)
    title = re.search(r"Product Title: (.+)", chunk)

    brand_val = brand.group(1).strip() if brand else "Unknown"
    ptype_val = ptype.group(1).strip() if ptype else "Unknown"

    if ptype_val == "Unknown" and title:
        title_text = title.group(1).lower()
        if "motherboard" in title_text:
            ptype_val = "Motherboard"
        elif "adapter" in title_text:
            ptype_val = "Adapter"
        elif "router" in title_text:
            ptype_val = "Router"
        elif "processor" in title_text or "cpu" in title_text:
            ptype_val = "Processor"
        elif "led strip" in title_text or "light" in title_text:
            ptype_val = "Lighting"

    return {
        "search_term": search_query,
        "brand": brand_val,
        "type": ptype_val
    }

def build_chroma_vectorstore(search_query: str, clear_existing: bool = False):
    print(f"[INFO] Building Chroma vector DB for: {search_query}")
    raw_text = web_scraper.text_data(search_query)
    product_blocks = parse_products(raw_text)
    chunks = [web_scraper.clean_text(p) for p in product_blocks]

    embedder = get_embedder()
    vectordb = Chroma(
        collection_name="pc_parts_embeddings",
        embedding_function=embedder,
        persist_directory=CHROMA_DIR
    )

    if clear_existing:
        try:
            vectordb.delete_collection()
            print("[INFO] Cleared previous Chroma collection.")
        except Exception as e:
            print(f"[WARN] Could not clear collection: {e}")

    metadatas = [extract_metadata(chunk, search_query) for chunk in chunks]
    ids = [str(uuid4()) for _ in chunks]

    vectordb.add_texts(
        texts=chunks,
        metadatas=metadatas,
        ids=ids
    )
    print(f"[INFO] Stored {len(chunks)} documents in vector DB.")

def search_chroma_vectorstore(query: str, top_k: int = 5, filter_type: Optional[str] = None):
    embedder = get_embedder()
    vectordb = Chroma(
        collection_name="pc_parts_embeddings",
        embedding_function=embedder,
        persist_directory=CHROMA_DIR
    )

    filters = {"type": filter_type} if filter_type else None

    results = vectordb.similarity_search(
        query,
        k=top_k,
        filter=filters
    )

    return [
        {"text": r.page_content, "metadata": r.metadata}
        for r in results
    ]
