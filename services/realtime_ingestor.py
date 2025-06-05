import os
from uuid import uuid4
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings.azure_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from pydantic import model_validator
import web_scraper
import re

class FixedAzureOpenAIEmbeddings(AzureOpenAIEmbeddings):
    @model_validator(mode="before")
    def add_default_validate_base_url(cls, values):
        if "validate_base_url" not in values:
            values["validate_base_url"] = True
        return values

# Azure OpenAI configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "***REMOVED***")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://internship2025-teama.openai.azure.com/")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AZURE_API_VERSION = "2025-01-01-preview"

CHROMA_DIR = "./chroma_store"

# Helper
def parse_products(raw_text: str):
    # Split based on a consistent delimiter between products
    products = raw_text.strip().split("\n\n")
    return [p.strip() for p in products if len(p.strip()) > 30]  # Drop tiny scraps


def get_embedder():
    print("[DEBUG] Initializing embedder...")
    embedder = FixedAzureOpenAIEmbeddings(
        deployment=AZURE_EMBEDDING_DEPLOYMENT,
        openai_api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        openai_api_version=AZURE_API_VERSION,
        chunk_size=1024,
    )
    print("[DEBUG] Embedder initialized with deployment:", AZURE_EMBEDDING_DEPLOYMENT)
    return embedder

def extract_metadata(chunk, search_query):
    brand = re.search(r"Brand: (.+)", chunk)
    ptype = re.search(r"Type: (.+)", chunk)
    title = re.search(r"Product Title: (.+)", chunk)

    # Basic metadata
    brand_val = brand.group(1).strip() if brand else "Unknown"
    ptype_val = ptype.group(1).strip() if ptype else "Unknown"

    # Fallback to keyword search in title if Type unknown
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
        # Add more as you see fit

    return {
        "search_term": search_query,
        "brand": brand_val,
        "type": ptype_val
    }


def main_flow(search_query):
    print(f"[DEBUG] Query: {search_query}")
    # Clear existing collection (optional for fresh start)
    try:
        Chroma(
            collection_name="pc_parts_embeddings",
            persist_directory=CHROMA_DIR
        ).delete_collection()
        print("[DEBUG] Cleared previous Chroma collection.")
    except Exception as e:
        print(f"[DEBUG] No previous collection to clear: {e}")

    raw_text = web_scraper.text_data(search_query)
    product_blocks = parse_products(raw_text)
    
    # Clean and filter
    chunks = [web_scraper.clean_text(p) for p in product_blocks if len(p.strip()) > 30]
    print(f"[DEBUG] Cleaned {len(chunks)} product chunks")

    embedder = get_embedder()
    vectordb = Chroma(
        collection_name="pc_parts_embeddings",
        embedding_function=embedder,
        persist_directory=CHROMA_DIR
    )

    # Metadata extraction
    metadata_list = metadata_list = [extract_metadata(chunk, search_query) for chunk in chunks]

    ids = [str(uuid4()) for _ in chunks]
    vectordb.add_texts(texts=chunks, metadatas=metadata_list, ids=ids)
    print(f"[DEBUG] Stored {len(chunks)} products in Chroma")
    return len(chunks)


def retrieve_relevant_chunks(query, top_k=5, filter_type=None):
    embedder = get_embedder()
    vectordb = Chroma(
        collection_name="pc_parts_embeddings",
        embedding_function=embedder,
        persist_directory=CHROMA_DIR
    )

    # Add filters if required, based on use case
    filters = None
    if filter_type:
        filters = {"type": filter_type}  # filter on 'type' metadata

    results = vectordb.similarity_search(
        query,
        k=top_k,
        filter=filters
    )

    return [{
        "text": r.page_content,
        "metadata": r.metadata
    } for r in results]



if __name__ == "__main__":
    user_query = "best AM5 motherboard with Wi-Fi support"
    main_flow(user_query)

    # Then, query retrieval:
    matches = retrieve_relevant_chunks(user_query)
    print(f"[DEBUG] Retrieved matches:\n{matches}")
