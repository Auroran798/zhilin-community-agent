import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.database import SessionLocal
from api.models import KnowledgeDocument
from rag.service import ingest
db=SessionLocal()
for doc in db.query(KnowledgeDocument).all(): print(doc.document_no, ingest(db,doc))
