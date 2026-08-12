"""Import every registered official or synthetic source and build its index."""
import sys
import csv
import argparse
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.database import SessionLocal
from api.models import User, KnowledgeDocument, KnowledgeSource
from rag.service import digest, ingest

ROOT=Path("data/knowledge")
def date(value): return datetime.fromisoformat(value) if value else None
def truth(value, default=False): return str(value or str(default)).strip().lower() in {"1","true","yes","y"}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--reindex-all",action="store_true");args=parser.parse_args()
    db=SessionLocal(); manager=db.query(User).filter_by(role="manager").first()
    if not manager: raise SystemExit("Run data.seed first")
    with (ROOT/"source_registry.csv").open(encoding="utf-8-sig",newline="") as handle:
        for record in csv.DictReader(handle):
            path=ROOT/record["local_path"]
            if not path.exists(): print(f"missing {path}"); continue
            payload=path.read_bytes(); h=digest(payload); official=record["source_type"]=="official_public_document"
            source=(db.query(KnowledgeSource).filter_by(source_no=record["source_no"]).first()
                    or db.query(KnowledgeSource).filter_by(source_url=record["source_url"]).first())
            governed=dict(data_class=record.get("data_class") or ("KB_POLICY" if official else "DEMO_SYNTHETIC"),country=record.get("country") or None,language=record.get("language") or "zh-CN",answerable=truth(record.get("answerable"),True),authority_level=record.get("authority_level") or ("government" if official else "community"),license_url=record.get("license_url") or None,contains_personal_data=truth(record.get("contains_personal_data")),minimization_rule=record.get("minimization_rule") or None,parser_version=record.get("parser_version") or "structured-v1",review_status=record.get("review_status") or ("approved" if truth(record.get("manually_verified")) else "pending"),translation_provider=record.get("translation_provider") or None,translation_model=record.get("translation_model") or None,translation_version=record.get("translation_version") or None)
            values=dict(title=record["title"],source_type=record["source_type"],source_url=record["source_url"],publisher=record["publisher"],publication_date=date(record["publication_date"]),version=record["version"],effective_date=date(record["effective_date"]),expiry_date=date(record["expiry_date"]),authority_status=record["authority_status"],jurisdiction=record["jurisdiction"],file_type=path.suffix.lstrip("."),file_hash=h,license_note=record["license_note"],actually_downloaded=truth(record["actually_downloaded"]),manually_verified=truth(record["manually_verified"]),notes=record["notes"],**governed)
            if source:
                source.source_no=record["source_no"]
                for k,v in values.items(): setattr(source,k,v)
            else:
                source=KnowledgeSource(source_no=record["source_no"],**values); db.add(source)
            db.commit(); db.refresh(source)
            doc=db.query(KnowledgeDocument).filter_by(file_hash=h).first()
            doc_values=dict(title=record["title"],document_type=record["document_type"],source_type=record["source_type"],source_id=source.id,source_url=record["source_url"],publisher=record["publisher"],jurisdiction=record["jurisdiction"],publication_date=date(record["publication_date"]),acquired_at=date(record["acquired_at"]),authority_status=record["authority_status"],license_note=record["license_note"],applicable_community=None if official else record["jurisdiction"],version=record["version"],effective_date=date(record["effective_date"]),expiry_date=date(record["expiry_date"]),file_name=path.name,file_type=path.suffix.lstrip("."),file_size=len(payload),file_hash=h,storage_path=str(path),is_authoritative=official,is_synthetic=not official,**governed)
            if doc:
                for k,v in doc_values.items(): setattr(doc,k,v)
                db.commit()
            else:
                doc=KnowledgeDocument(document_no=f"KD-{record['source_no'].replace('SRC-','')}",created_by=manager.id,status="uploaded",**doc_values); db.add(doc); db.commit()
            if args.reindex_all or doc.status not in {"indexed","active"}: ingest(db,doc)
            # The registry is the controlled import queue.  Only sources that
            # were manually verified may be released automatically; ad-hoc UI
            # uploads still go through the review endpoints.
            if record["manually_verified"].lower()=="true" and truth(record.get("answerable")):
                doc.status="active"; db.commit()
            print(f"indexed {path}: {doc.status}")
if __name__=="__main__": main()
