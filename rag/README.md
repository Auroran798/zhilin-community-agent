# RAG

Stage 2 uses file-hash deduplication, parsers for PDF/DOCX/TXT/Markdown/HTML, deterministic chunk IDs, SQLite metadata, and a persistent Chroma collection when `chromadb` is installed. The deterministic hashing embedding is an offline fallback intended for demos/tests, not a semantic production model.
