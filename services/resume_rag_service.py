# ============================================================
# Resume RAG Service — Semantic Chunking & Retrieval from ChromaDB
# ============================================================
# PURPOSE:
#   Instead of comparing a job posting against a single short summary
#   of your resume, this service uses RAG (Retrieval-Augmented Generation):
#
#   1. INGESTION (Semantic Chunking):
#      Divides your resume into logical sections:
#        • Summary & Core Profile
#        • Technical Skills (LLMs, GenAI, LangChain, Vector DBs, etc.)
#        • Work Experience (Production RAG systems, FastAPI, etc.)
#        • Key Projects (Agentic workflows, NLP pipelines)
#        • Education & Certifications
#      Each section is converted to a 384-dimensional vector using our
#      local sentence-transformers model and stored in ChromaDB.
#
#   2. RETRIEVAL (Querying by Job Description):
#      When analyzing a job posting (e.g. "Looking for LangGraph & pgvector dev"),
#      we query ChromaDB to fetch the top 3 most relevant chunks from YOUR resume.
#      Those exact pieces of evidence are used to compute match scores and
#      fed into the LLM (NVIDIA NIM / Gemini / OpenAI) for deep rationale generation!
#
# USAGE:
#   from services.resume_rag_service import get_rag_service
#
#   rag = get_rag_service()
#   rag.ingest_resume("path/to/resume.pdf")
#
#   # For a job description, retrieve relevant resume chunks:
#   chunks = rag.retrieve_relevant_chunks("We need experience with LangChain and RAG...", top_k=3)
# ============================================================

import os
import re
from typing import List, Dict, Optional
import chromadb
from services.embedding_service import get_embedder
from agents.resume_agent import ResumeAgent


class ResumeRagService:
    """
    Manages semantic chunking and RAG retrieval for the user's resume in ChromaDB.
    """

    def __init__(self, persist_directory: str = "./data/chroma"):
        """
        Initialize the ChromaDB persistent client and collection for resume chunks.
        """
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Get or create dedicated collection for resume sections
        self.collection = self.client.get_or_create_collection(
            name="user_resume_chunks",
            metadata={"description": "Semantic sections of user resume for RAG retrieval"},
        )

        self.embedder = get_embedder()
        self.resume_agent = ResumeAgent()
        print(f"[ResumeRAG] Initialized with {self.collection.count()} existing resume chunks in ChromaDB")

    # ================================================================
    # INGESTION — Chunk Resume & Store in ChromaDB
    # ================================================================

    def ingest_resume(self, file_path: str) -> int:
        """
        Extract text from a resume PDF/DOCX, perform semantic section chunking,
        convert each chunk to a vector embedding, and store in ChromaDB.
        
        Args:
            file_path: Absolute path to the resume file (e.g., Anurag's PDF)
            
        Returns:
            Number of semantic chunks stored in ChromaDB
        """
        print(f"\n[ResumeRAG] Starting ingestion for: {file_path}")
        
        # 1. Extract raw text from file
        raw_text = self.resume_agent.extract_text(file_path)
        if not raw_text:
            print("[ResumeRAG] ERROR: Could not extract text from file.")
            return 0

        # 2. Also parse structured profile and save to SQLite database
        print("[ResumeRAG] Parsing structured profile for SQLite storage...")
        try:
            self.resume_agent.parse_resume(file_path)
        except Exception as e:
            print(f"[ResumeRAG] Note: LLM structured parsing skipped/failed ({e}). Proceeding with RAG chunk ingestion.")

        # 3. Perform semantic section chunking
        chunks = self._semantic_chunking(raw_text)
        print(f"[ResumeRAG] Divided resume into {len(chunks)} semantic chunks:")
        for idx, chunk in enumerate(chunks):
            print(f"  -> Chunk {idx+1} [{chunk['section']}]: {chunk['content'][:80]}...")

        # 4. Clear old resume chunks from ChromaDB (to prevent stale data)
        self.clear_chunks()

        # 5. Embed and store new chunks in ChromaDB
        ids = []
        documents = []
        metadatas = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"resume_chunk_{idx+1}"
            ids.append(chunk_id)
            documents.append(chunk["content"])
            metadatas.append({
                "section": chunk["section"],
                "char_count": len(chunk["content"]),
                "source_file": os.path.basename(file_path)
            })

        print(f"[ResumeRAG] Generating vector embeddings for {len(documents)} chunks...")
        embeddings = self.embedder.embed_batch(documents)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        print(f"[ResumeRAG] Successfully stored {len(ids)} resume chunks in ChromaDB!")
        return len(ids)

    def _semantic_chunking(self, raw_text: str) -> List[Dict[str, str]]:
        """
        Semantically divides a resume into logical sections based on common headings.
        If headings aren't cleanly detected, uses paragraph-based fallback chunking.
        """
        # Common uppercase or header-style section dividers in tech resumes
        section_patterns = [
            r"\n(?=SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|ABOUT ME)",
            r"\n(?=SKILLS|TECHNICAL SKILLS|TECHNOLOGIES|COMPETENCIES)",
            r"\n(?=EXPERIENCE|WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|EMPLOYMENT)",
            r"\n(?=PROJECTS|KEY PROJECTS|ACADEMIC PROJECTS|PERSONAL PROJECTS)",
            r"\n(?=EDUCATION|ACADEMICS|QUALIFICATIONS)",
            r"\n(?=CERTIFICATIONS|ACHIEVEMENTS|AWARDS|PUBLICATIONS)"
        ]

        # Combine patterns into a single split regex
        combined_pattern = "|".join(section_patterns)
        raw_sections = re.split(combined_pattern, raw_text, flags=re.IGNORECASE)

        chunks = []
        for sec in raw_sections:
            clean_sec = sec.strip()
            if not clean_sec or len(clean_sec) < 30:
                continue

            # Detect section title from first line
            lines = clean_sec.split("\n")
            first_line = lines[0].strip().upper()
            
            section_name = "GENERAL / OTHER"
            if any(h in first_line for h in ["SUMMARY", "OBJECTIVE", "ABOUT"]):
                section_name = "SUMMARY"
            elif any(h in first_line for h in ["SKILLS", "TECHNOLOGIES", "COMPETENCIES"]):
                section_name = "TECHNICAL SKILLS"
            elif any(h in first_line for h in ["EXPERIENCE", "EMPLOYMENT", "WORK"]):
                section_name = "WORK EXPERIENCE"
            elif any(h in first_line for h in ["PROJECTS"]):
                section_name = "PROJECTS"
            elif any(h in first_line for h in ["EDUCATION", "ACADEMICS"]):
                section_name = "EDUCATION"
            elif any(h in first_line for h in ["CERTIFICATION", "AWARD", "ACHIEVEMENT"]):
                section_name = "CERTIFICATIONS"
            else:
                # If first line looks like a header, use it
                if len(first_line) < 40 and not first_line.endswith("."):
                    section_name = first_line

            # If a section is extremely long (>1500 chars, e.g. many projects), sub-chunk it by paragraphs
            if len(clean_sec) > 1500:
                sub_paragraphs = clean_sec.split("\n\n")
                current_sub = ""
                sub_idx = 1
                for para in sub_paragraphs:
                    if len(current_sub) + len(para) > 800:
                        if current_sub.strip():
                            chunks.append({
                                "section": f"{section_name} (Part {sub_idx})",
                                "content": current_sub.strip()
                            })
                            sub_idx += 1
                        current_sub = para + "\n\n"
                    else:
                        current_sub += para + "\n\n"
                if current_sub.strip():
                    chunks.append({
                        "section": f"{section_name} (Part {sub_idx})" if sub_idx > 1 else section_name,
                        "content": current_sub.strip()
                    })
            else:
                chunks.append({
                    "section": section_name,
                    "content": clean_sec
                })

        # Fallback if no clear sections were detected
        if not chunks:
            print("[ResumeRAG] Warning: Could not detect clear section headers. Using 500-character paragraph chunking.")
            step = 450
            for i in range(0, len(raw_text), step):
                chunk_text = raw_text[i:i+550].strip()
                if len(chunk_text) >= 30:
                    chunks.append({
                        "section": f"Resume Chunk {len(chunks)+1}",
                        "content": chunk_text
                    })

        return chunks

    # ================================================================
    # RETRIEVAL — Fetch Relevant Resume Evidence for a Job
    # ================================================================

    def retrieve_relevant_chunks(
        self,
        job_description: str,
        top_k: int = 3
    ) -> List[Dict[str, any]]:
        """
        Given a job description (or required skills text), query ChromaDB
        to find the top-K most semantically relevant chunks from your resume.
        
        Args:
            job_description: The text of the job posting
            top_k: Number of resume chunks to retrieve (default: 3)
            
        Returns:
            List of dicts containing: section, content, similarity_score
        """
        if self.collection.count() == 0:
            print("[ResumeRAG] Warning: No resume chunks in ChromaDB. Run ingest_resume() first.")
            return []

        actual_k = min(top_k, self.collection.count())
        
        # Embed the job description query
        query_embedding = self.embedder.embed(job_description[:2000])  # limit query length for speed

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            # Convert cosine distance to similarity score (0.0 to 1.0)
            similarity = max(0.0, float(1.0 - distance))

            retrieved.append({
                "id": results["ids"][0][i],
                "section": results["metadatas"][0][i].get("section", "Unknown Section"),
                "content": results["documents"][0][i],
                "similarity_score": round(similarity, 4),
            })

        return retrieved

    def get_count(self) -> int:
        """Return number of stored resume chunks."""
        return self.collection.count()

    def clear_chunks(self) -> None:
        """Delete all resume chunks from ChromaDB."""
        self.client.delete_collection("user_resume_chunks")
        self.collection = self.client.get_or_create_collection(
            name="user_resume_chunks",
            metadata={"description": "Semantic sections of user resume for RAG retrieval"},
        )
        print("[ResumeRAG] Cleared existing resume chunks from ChromaDB")


# ============================================================
# GLOBAL INSTANCE (lazy initialization)
# ============================================================

_rag_service_instance: Optional[ResumeRagService] = None


def get_rag_service() -> ResumeRagService:
    """
    Get or create the global Resume RAG Service instance.
    """
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = ResumeRagService()
    return _rag_service_instance
