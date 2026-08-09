from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base
from api.models import User, Property, WorkOrder, Bill, PaymentRecord, InspectionTask, InspectionRecord, RectificationOrder
import data.seed as seed_data

def test_seed_is_repeatable_and_complete(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_data.command, "upgrade", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_data, "SessionLocal", Session)
    seed_data.seed()
    db = Session()
    first = (db.query(User).count(), db.query(Property).count(), db.query(WorkOrder).count(), db.query(Bill).count())
    assert first == (133, 120, 100, 96)
    assert db.query(PaymentRecord).count() == 48
    assert db.query(InspectionTask).count() == 14
    assert db.query(InspectionRecord).count() == 10
    assert db.query(RectificationOrder).count() == 8
    db.close()
    seed_data.seed()
    db = Session()
    assert (db.query(User).count(), db.query(Property).count(), db.query(WorkOrder).count(), db.query(Bill).count()) == first
    db.close()

