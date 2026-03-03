import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

load_dotenv()

# Configuration
QDRANT_URL        = os.getenv("QDRANT_URL")
QDRANT_API_KEY    = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME   = "network_guide"
EMBED_MODEL       = "text-embedding-3-small"
CHUNK_SIZE        = 500
CHUNK_OVERLAP     = 100

def ingest():
    # 1 — Load the guide
    loader = TextLoader("raw_data/network_architecture_EDIN_DETAILED.txt")
    docs = loader.load()
    print(f"Loaded document: {len(docs[0].page_content)} characters")

    # 2 — Chunk
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    split_documents = text_splitter.split_documents(docs)
    print(f"Split into {len(split_documents)} chunks")

    # 3 — Connect to Qdrant Cloud
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # 4 — Recreate collection (wipes old data on re-ingest)
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )
    print(f"Created collection: {COLLECTION_NAME}")

    # 5 — Embed and upsert
    embeddings = OpenAIEmbeddings(
        model=EMBED_MODEL,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )
    vector_store.add_documents(documents=split_documents)
    print(f"Upserted {len(split_documents)} chunks to Qdrant Cloud ✅")

if __name__ == "__main__":
    ingest()