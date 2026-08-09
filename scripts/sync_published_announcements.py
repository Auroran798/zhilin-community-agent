"""Index only currently published, non-expired stage-1 announcements."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime
from api.database import SessionLocal
from api.models import Announcement, User
from rag.service import sync_published_announcement

db=SessionLocal(); manager=db.query(User).filter_by(role="manager").first()
for item in db.query(Announcement).filter_by(status="published"):
    doc=sync_published_announcement(db,item,manager.id)
    print(item.id, getattr(doc,"document_no", "skipped"))
