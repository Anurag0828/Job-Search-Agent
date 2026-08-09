# ============================================================
# Vector Store — ChromaDB Wrapper for Semantic Search
# ============================================================
# PURPOSE:
#   Stores and searches vector embeddings using ChromaDB.
#   This is how we quickly find jobs that are semantically similar
#   to the user's profile, without sending every job to the LLM.
#
# HOW IT FITS IN THE PIPELINE:
#   500 raw jobs collected
#        │
#        ▼
#   [Embedding Service] converts each job description to a vector
#        │
#        ▼
#   [Vector Store (this file)] stores all vectors in ChromaDB
#        │
#        ▼
#   User profile → vector → query ChromaDB → "find top 30 similar jobs"
#        │
#        ▼
#   30 best candidates sent to LLM for detailed scoring
#
# WHY CHROMADB?
#   - Lightweight (runs as a library, no server needed)
#   - Persistent (data survives app restarts)
#   - Fast (finds similar vectors in milliseconds)
#   - Simple API (add, query, delete)
#
# USAGE:
#   from services.vector_store import get_vector_store
#
#   store = get_vector_store()
#   store.add_jobs(job_list)           # Store job embeddings
#   results = store.find_similar(      # Search for similar jobs
#       profile_text="Python developer with 5 years experience",
#       top_k=30
#   )
# ============================================================

import os
from typing import Optional
import chromadb
from services.embedding_service import get_embedder


class VectorStore:
    """
    ChromaDB-based vector store for semantic job matching.
    
    Stores job description embeddings and enables fast
    similarity search against the user's profile.
    """

    def __init__(self, persist_directory: str = "./data/chroma"):
        """
        Initialize the vector store.
        
        Args:
            persist_directory: Where ChromaDB stores its data on disk.
                             Data persists across app restarts.
        """
        # Ensure the directory exists
        os.makedirs(persist_directory, exist_ok=True)

        # Create the ChromaDB client (persistent storage)
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Get or create our job embeddings collection
        # A "collection" in ChromaDB is like a table in a database
        self.collection = self.client.get_or_create_collection(
            name="job_postings",
            metadata={"description": "Job posting embeddings for semantic matching"},
        )

        # Get the embedding service
        self.embedder = get_embedder()

        print(f"[VectorStore] Initialized with {self.collection.count()} existing embeddings")

    # ================================================================
    # ADD — Store job embeddings
    # ================================================================

    def add_jobs(self, jobs: list[dict]) -> int:
        """
        Add job postings to the vector store.
        
        Each job gets:
        1. Converted to text (title + company + description)
        2. Text converted to a vector embedding
        3. Vector stored in ChromaDB with metadata
        
        Args:
            jobs: List of job dictionaries with at least 'title' and 'url'
        
        Returns:
            Number of jobs successfully added
        
        Example:
            store.add_jobs([
                {"title": "Python Dev", "company": "Google", "description": "...", "url": "..."},
                {"title": "React Dev", "company": "Meta", "description": "...", "url": "..."},
            ])
        """
        if not jobs:
            return 0

        print(f"[VectorStore] Adding {len(jobs)} jobs...")

        # Prepare data for ChromaDB
        ids = []          # Unique ID for each job
        documents = []    # The text to embed
        metadatas = []    # Extra data stored alongside each embedding

        for i, job in enumerate(jobs):
            # Create a unique ID (using URL hash to avoid duplicates)
            job_id = f"job_{hash(job.get('url', str(i)))}"

            # Check if this job is already in the store
            existing = self.collection.get(ids=[job_id])
            if existing and existing["ids"]:
                continue  # Skip — already stored

            # Create the text to embed
            text = self.embedder.create_job_text(job)

            # Store metadata so we can retrieve job details later
            metadata = {
                "title": job.get("title", "")[:500],
                "company": job.get("company", "")[:200],
                "location": job.get("location", "")[:200],
                "url": job.get("url", ""),
                "platform": job.get("platform", ""),
            }

            ids.append(job_id)
            documents.append(text)
            metadatas.append(metadata)

        if not ids:
            print(f"[VectorStore] No new jobs to add (all already exist)")
            return 0

        # Batch embed all texts at once (much faster than one-by-one)
        embeddings = self.embedder.embed_batch(documents)

        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        print(f"[VectorStore] Added {len(ids)} new jobs. Total: {self.collection.count()}")
        return len(ids)

    # ================================================================
    # SEARCH — Find jobs similar to the user's profile
    # ================================================================

    def find_similar(
        self,
        profile_text: str,
        top_k: int = 30,
    ) -> list[dict]:
        """
        Find the top-K jobs most similar to the user's profile.
        
        This is the FAST first pass of matching:
        - Embeds the profile text into a vector
        - Searches ChromaDB for the closest job vectors
        - Returns the top matches with similarity scores
        
        Args:
            profile_text: Text representation of the user's profile
                         (created by EmbeddingService.create_profile_text)
            top_k: How many results to return (default: 30)
        
        Returns:
            List of dicts with keys: id, title, company, location,
            url, platform, similarity_score, document
        
        Example:
            results = store.find_similar(
                "Senior Python developer with FastAPI, 5 years experience",
                top_k=30
            )
            for r in results:
                print(f"{r['title']} @ {r['company']} — similarity: {r['similarity_score']:.2f}")
        """
        if self.collection.count() == 0:
            print("[VectorStore] No jobs in the store yet")
            return []

        # Limit top_k to the number of jobs we actually have
        actual_k = min(top_k, self.collection.count())

        # Embed the profile text
        profile_embedding = self.embedder.embed(profile_text)

        # Query ChromaDB for most similar jobs
        results = self.collection.query(
            query_embeddings=[profile_embedding],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        # Format results into a clean list of dicts
        formatted = []
        for i in range(len(results["ids"][0])):
            # ChromaDB returns "distances" — lower = more similar
            # Convert to similarity score: 1 - distance (higher = better)
            distance = results["distances"][0][i]
            similarity = max(0, 1 - distance)  # Ensure non-negative

            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "similarity_score": round(similarity, 4),
                **results["metadatas"][0][i],  # title, company, url, etc.
            })

        print(f"[VectorStore] Found {len(formatted)} similar jobs "
              f"(best score: {formatted[0]['similarity_score']:.3f})" if formatted else "")

        return formatted

    # ================================================================
    # UTILITY METHODS
    # ================================================================

    def get_count(self) -> int:
        """Return the total number of job embeddings stored."""
        return self.collection.count()

    def clear(self) -> None:
        """
        Delete ALL job embeddings from the store.
        Useful for testing or starting fresh.
        """
        # Delete the collection and recreate it
        self.client.delete_collection("job_postings")
        self.collection = self.client.get_or_create_collection(
            name="job_postings",
            metadata={"description": "Job posting embeddings for semantic matching"},
        )
        print("[VectorStore] Cleared all embeddings")


# ============================================================
# GLOBAL INSTANCE (lazy initialization)
# ============================================================

_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    Get or create the global vector store instance.
    
    Usage:
        from services.vector_store import get_vector_store
        store = get_vector_store()
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance
