"""Purge expired query logs and their feedback according to configured retention."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.config import settings
from api.database import SessionLocal
from api.models import RagFeedback, RagQueryLog
from api.time import utc_now

def main():
    db=SessionLocal(); cutoff=utc_now()-timedelta(days=settings.rag_query_log_retention_days)
    ids=[row.id for row in db.query(RagQueryLog.id).filter(RagQueryLog.created_at<cutoff)]
    if ids:
        db.query(RagFeedback).filter(RagFeedback.rag_query_log_id.in_(ids)).delete(synchronize_session=False)
        db.query(RagQueryLog).filter(RagQueryLog.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    print(f"purged {len(ids)} RAG query logs before {cutoff.isoformat()}")
    db.close()
if __name__=="__main__": main()
