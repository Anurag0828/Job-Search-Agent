# ============================================================
# Embedding Service — Converts Text to Vectors
# ============================================================
# PURPOSE:
#   Converts text (resume, job descriptions) into numerical vectors
#   (lists of numbers) that capture the MEANING of the text.
#
# WHY WE NEED THIS:
#   Computers can't compare "Python developer" and "Backend engineer"
#   as text — they're completely different strings.
#   
#   But as VECTORS (numbers that capture meaning):
#     "Python developer"  → [0.82, 0.15, 0.91, 0.33, ...]
#     "Backend engineer"  → [0.79, 0.18, 0.88, 0.31, ...]
#     "Pastry chef"       → [0.12, 0.95, 0.05, 0.88, ...]
#   
#   Now we can COMPUTE similarity:
#     "Python developer" vs "Backend engineer" = 0.92 (very similar!)
#     "Python developer" vs "Pastry chef"      = 0.11 (not similar)
#
# HOW IT WORKS:
#   We use a pre-trained model called "all-MiniLM-L6-v2" that:
#   - Runs LOCALLY on your computer (no API calls, no cost)
#   - Downloads once (~90MB), then works offline
#   - Converts any text into a 384-dimensional vector
#   - Is specifically trained to capture semantic meaning
#
# USAGE:
#   from services.embedding_service import get_embedder
#   
#   embedder = get_embedder()
#   vector = embedder.embed("Senior Python Developer with FastAPI experience")
#   vectors = embedder.embed_batch(["job desc 1", "job desc 2", "job desc 3"])
# ============================================================

from typing import Optional
import numpy as np


class EmbeddingService:
    """
    Converts text into vector embeddings using a local model.
    
    The model (all-MiniLM-L6-v2) runs on your CPU — no GPU needed,
    no API key needed, no internet needed (after first download).
    
    First call downloads the model (~90MB). Subsequent calls are instant.
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the embedding service. Supports local sentence-transformers
        and NVIDIA NIM API endpoints (e.g., nvidia/nemotron-3-embed-1b).
        """
        from config.settings import settings
        self.provider = settings.EMBEDDING_PROVIDER
        
        if model_name:
            self.model_name = model_name
        elif self.provider == "nvidia":
            self.model_name = settings.NVIDIA_EMBED_MODEL
        else:
            self.model_name = "all-MiniLM-L6-v2"
            
        self._model = None
        self._nvidia_client = None
        print(f"[Embedder] Initialized with provider '{self.provider}' and model: {self.model_name}")

    @property
    def nvidia_client(self):
        """Lazy-load NVIDIA NIM OpenAI-compatible client."""
        if self._nvidia_client is None:
            import openai
            from config.settings import settings
            if not settings.NVIDIA_API_KEY:
                raise ValueError("NVIDIA_API_KEY is required when EMBEDDING_PROVIDER='nvidia'. Get one at https://build.nvidia.com")
            self._nvidia_client = openai.OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=settings.NVIDIA_API_KEY
            )
        return self._nvidia_client

    @property
    def model(self):
        """Lazy-load local sentence-transformers model."""
        if self._model is None:
            print(f"[Embedder] Loading local model '{self.model_name}'...")
            print(f"[Embedder] (First time? This downloads ~90MB. After that, it's instant.)")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            print(f"[Embedder] Model loaded successfully!")
        return self._model

    def embed(self, text: str) -> list[float]:
        """Convert a single text string into a vector embedding."""
        if self.provider == "nvidia" or self.model_name.startswith("nvidia/") or "nemotron" in self.model_name:
            res = self.nvidia_client.embeddings.create(
                input=text[:2048],
                model=self.model_name,
                encoding_format="float"
            )
            return res.data[0].embedding
            
        embedding = self.model.encode(text, show_progress_bar=False)
        return embedding.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Convert multiple texts into vectors at once."""
        if not texts:
            return []

        print(f"[Embedder] Embedding {len(texts)} texts...")
        if self.provider == "nvidia" or self.model_name.startswith("nvidia/") or "nemotron" in self.model_name:
            results = []
            # Process in batches of 16 for API endpoints
            for i in range(0, len(texts), 16):
                batch = [t[:2048] for t in texts[i:i+16]]
                res = self.nvidia_client.embeddings.create(
                    input=batch,
                    model=self.model_name,
                    encoding_format="float"
                )
                results.extend([d.embedding for d in res.data])
            return results

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 10,
        )
        return [e.tolist() for e in embeddings]

    def similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        """
        Compute how similar two vectors are (cosine similarity).
        
        Returns a number between -1 and 1:
            1.0  = identical meaning
            0.5+ = somewhat similar
            0.0  = unrelated
           -1.0  = opposite meaning
        
        Example:
            score = embedder.similarity(
                embedder.embed("Python backend developer"),
                embedder.embed("Senior Python engineer")
            )
            # score ≈ 0.89 (very similar!)
        """
        a = np.array(vector_a)
        b = np.array(vector_b)

        # Cosine similarity = dot product / (magnitude_a * magnitude_b)
        dot_product = np.dot(a, b)
        magnitude_a = np.linalg.norm(a)
        magnitude_b = np.linalg.norm(b)

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return float(dot_product / (magnitude_a * magnitude_b))

    def create_profile_text(self, profile_data: dict) -> str:
        """
        Convert a user profile into a single text string for embedding.
        
        The embedding model works best with natural text, so we combine
        the structured profile fields into a readable paragraph.
        
        Args:
            profile_data: Dictionary with user profile fields
        
        Returns:
            A text summary suitable for embedding
        
        Example:
            text = embedder.create_profile_text({
                "skills": ["Python", "FastAPI"],
                "preferred_roles": ["Backend Engineer"],
                "experience_years": 5,
                "seniority": "senior"
            })
            # Returns: "senior professional with 5 years of experience.
            #           Skills: Python, FastAPI. Looking for: Backend Engineer."
        """
        parts = []

        # Seniority and experience
        seniority = profile_data.get("seniority", "")
        experience = profile_data.get("experience_years", "")
        if seniority or experience:
            parts.append(f"{seniority} professional with {experience} years of experience")

        # Skills
        skills = profile_data.get("skills", [])
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")

        # Preferred roles
        roles = profile_data.get("preferred_roles", [])
        if roles:
            parts.append(f"Looking for: {', '.join(roles)}")

        # Summary
        summary = profile_data.get("summary", "")
        if summary:
            parts.append(summary)

        return ". ".join(parts)

    def create_job_text(self, job_data: dict) -> str:
        """
        Convert a job posting into a single text string for embedding.
        
        Args:
            job_data: Dictionary with job posting fields
        
        Returns:
            A text summary suitable for embedding
        """
        parts = []

        title = job_data.get("title", "")
        if title:
            parts.append(title)

        company = job_data.get("company", "")
        if company:
            parts.append(f"at {company}")

        location = job_data.get("location", "")
        if location:
            parts.append(f"in {location}")

        description = job_data.get("description", "")
        if description:
            # Truncate very long descriptions (embedding model has limits)
            parts.append(description[:2000])

        return ". ".join(parts)


# ============================================================
# GLOBAL INSTANCE (lazy initialization)
# ============================================================

_embedder_instance: Optional[EmbeddingService] = None


def get_embedder() -> EmbeddingService:
    """
    Get or create the global embedding service instance.
    
    Usage:
        from services.embedding_service import get_embedder
        embedder = get_embedder()
    """
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = EmbeddingService()
    return _embedder_instance
