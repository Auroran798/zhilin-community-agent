"""Import every registered official or synthetic source and build its index."""
import sys
import csv
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.database import SessionLocal
from api.models import User, KnowledgeDocument, KnowledgeSource
from rag.service import digest, ingest

ROOT=Path("data/knowledge")
def date(value): return datetime.fromisoformat(value) if value else None

def main():
    db=SessionLocal(); manager=db.query(User).filter_by(role="manager").first()
    if not manager: raise SystemExit("Run data.seed first")
    with (ROOT/"source_registry.csv").open(encoding="utf-8",newline="") as handle:
        for record in csv.DictReader(handle):
            path=ROOT/record["local_path"]
            if not path.exists(): print(f"missing {path}"); continue
            payload=path.read_bytes(); h=digest(payload); official=record["source_type"]=="official_public_document"
            source=db.query(KnowledgeSource).filter_by(source_no=record["source_no"]).first()
            values=dict(title=record["title"],source_type=record["source_type"],source_url=record["source_url"],publisher=record["publisher"],publication_date=date(record["publication_date"]),version=record["version"],effective_date=date(record["effective_date"]),expiry_date=date(record["expiry_date"]),authority_status=record["authority_status"],jurisdiction=record["jurisdiction"],file_type=path.suffix.lstrip("."),file_hash=h,license_note=record["license_note"],actually_downloaded=record["actually_downloaded"].lower()=="true",manually_verified=record["manually_verified"].lower()=="true",notes=record["notes"])
            if source:
                for k,v in values.items(): setattr(source,k,v)
            else:
                source=KnowledgeSource(source_no=record["source_no"],**values); db.add(source)
            db.commit(); db.refresh(source)
            doc=db.query(KnowledgeDocument).filter_by(file_hash=h).first()
            doc_values=dict(title=record["title"],document_type=record["document_type"],source_type=record["source_type"],source_id=source.id,source_url=record["source_url"],publisher=record["publisher"],jurisdiction=record["jurisdiction"],publication_date=date(record["publication_date"]),acquired_at=date(record["acquired_at"]),authority_status=record["authority_status"],license_note=record["license_note"],applicable_community=None if official else record["jurisdiction"],version=record["version"],effective_date=date(record["effective_date"]),expiry_date=date(record["expiry_date"]),file_name=path.name,file_type=path.suffix.lstrip("."),file_size=len(payload),file_hash=h,storage_path=str(path),is_authoritative=official,is_synthetic=not official)
            if doc:
                for k,v in doc_values.items(): setattr(doc,k,v)
                db.commit()
            else:
                doc=KnowledgeDocument(document_no=f"KD-{record['source_no'].replace('SRC-','')}",created_by=manager.id,status="uploaded",**doc_values); db.add(doc); db.commit()
            if doc.status not in {"indexed","active"}: ingest(db,doc)
            # The registry is the controlled import queue.  Only sources that
            # were manually verified may be released automatically; ad-hoc UI
            # uploads still go through the review endpoints.
            if record["manually_verified"].lower()=="true":
                doc.status="active"; db.commit()
            print(f"indexed {path}: {doc.status}")
if __name__=="__main__": main()
