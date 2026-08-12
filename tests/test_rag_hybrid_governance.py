from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.models import KnowledgeChunk, KnowledgeDocument, User
from api.security import hash_password
from rag.service import HashEmbedding, _expand_query, _jurisdiction_conflicts, digest, quality_profile, search
from agent.tools import infer_jurisdiction


def test_hybrid_retrieval_exposes_diagnostics_and_excludes_non_answerable(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'hybrid.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
    manager=User(username="hybrid_manager",password_hash=hash_password("x"),display_name="M",role="manager");db.add(manager);db.flush()
    for index,answerable in enumerate((True,False),start=1):
        document=KnowledgeDocument(document_no=f"H-{index}",title="Complaint Handling Code" if answerable else "Unreviewed Notes",document_type="complaint_handling_code",source_type="official_public_document",source_url=f"https://official.example/{index}",publisher="Authority",country="GB",jurisdiction="GB",language="en",answerable=answerable,authority_level="statutory_code",review_status="approved",version="1",status="active",file_name=f"{index}.md",file_type="md",file_size=1,file_hash=str(index)*64,storage_path=f"{index}.md",created_by=manager.id)
        db.add(document);db.flush();text="stage one complaints must be acknowledged and logged" if answerable else "secret irrelevant notes"
        db.add(KnowledgeChunk(chunk_uid=digest(f"{index}:{text}".encode()),document_id=document.id,document_version="1",chunk_index=0,text=text,token_count=len(text),embedding_model=HashEmbedding.model_name,content_hash=digest(text.encode()),is_suspicious=False))
    db.commit()
    response=search(db,"stage one complaint acknowledged",manager,None,jurisdiction="GB")
    assert response["answer_status"]=="answered"
    assert {citation["title"] for citation in response["citations"]}=={"Complaint Handling Code"}
    assert {"bm25","dense","rrf","reranker"}<=response["evidence"][0]["retrieval"].keys()
    assert response["retrieval_mode"]=="rrf_hybrid"
    db.close()


def test_default_quality_profile_never_claims_formal_semantic_quality():
    profile=quality_profile()
    assert profile["mode"]=="offline_fallback"
    assert profile["formal_quality_claim_allowed"] is False


def test_agent_jurisdiction_router_is_explicit_and_deterministic():
    assert infer_jurisdiction("What does the Housing Ombudsman Complaint Handling Code require?")=="GB"
    assert infer_jurisdiction("Open311 GeoReport v2 的字段是什么？")=="GLOBAL"
    assert infer_jurisdiction("装修规则是什么？")==None


def test_governed_bilingual_expansion_and_conflict_detection():
    expanded=_expand_query("新南威尔士公共部位由谁维修？","AU-NSW")
    assert "common property" in expanded
    assert "owners corporation" in expanded
    assert _jurisdiction_conflicts("维多利亚州的规则是否适用于北京？","北京市")==["AU-VIC"]
    assert _jurisdiction_conflicts("北京住宅物业如何报修？","北京市")==[]
