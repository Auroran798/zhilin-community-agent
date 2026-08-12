from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.models import KnowledgeChunk, KnowledgeDocument, User
from api.security import hash_password
from rag.service import search


def test_rag_requires_jurisdiction_before_mixing_official_rules(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'jurisdiction.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    db=Session()
    manager=User(username="jurisdiction_manager",password_hash=hash_password("x"),display_name="M",role="manager")
    db.add(manager);db.flush()
    documents=[]
    for index,jurisdiction in enumerate(("US-NY-NYC","GB"),start=1):
        document=KnowledgeDocument(
            document_no=f"J-{index}",title=f"Heat repair rule {jurisdiction}",document_type="service_process",
            source_type="official_public_document",source_url=f"https://example.test/{index}",publisher="Official publisher",
            jurisdiction=jurisdiction,version="1.0",status="active",file_name=f"{index}.md",file_type="md",file_size=10,
            file_hash=f"{index:064d}",storage_path=f"{index}.md",created_by=manager.id,is_authoritative=True,is_synthetic=False,
        )
        db.add(document);db.flush()
        db.add(KnowledgeChunk(
            chunk_uid=f"chunk-{index}",document_id=document.id,document_version="1.0",chunk_index=0,
            text="heat repair response procedure",token_count=4,content_hash=f"{index:064d}",is_suspicious=False,
        ))
        documents.append(document)
    db.commit()

    ambiguous=search(db,"heat repair",manager,None)
    assert ambiguous["answer_status"]=="refused"
    assert "jurisdiction" in ambiguous["answer"]

    scoped=search(db,"heat repair",manager,None,jurisdiction="US-NY-NYC")
    assert scoped["answer_status"]=="answered"
    assert scoped["citations"]
    assert {item["jurisdiction"] for item in scoped["citations"]}=={"US-NY-NYC"}
    db.close()
