from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.models import KnowledgeChunk, KnowledgeDocument, User
from api.security import hash_password
from rag.service import HashEmbedding, _scope_decision, digest, requires_manual_confirmation, search

COMMUNITY="北京市合成示范社区"


def make_db(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'beijing-modes.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
    manager=User(username="beijing_manager",password_hash=hash_password("x"),display_name="M",role="manager");db.add(manager);db.flush()
    definitions=[
        ("N","全国物业服务费规则","全国",None,"national_law","物业服务人不得采取停止供水供电供热供燃气等方式催交物业费","KB_POLICY"),
        ("BJ","北京市公共收益公示规则","北京市",None,"local_regulation","北京市物业服务人应当公示公共收益和物业服务事项","KB_POLICY"),
        ("C","合成示范社区收费约定",COMMUNITY,COMMUNITY,"community_contract","本合成示范社区合同约定模拟物业服务费标准和复核流程","DEMO_SYNTHETIC"),
        ("GB","UK complaint comparison","GB",None,"statutory_code","Housing complaint handling code requires a staged complaint process","KB_POLICY"),
    ]
    for index,(number,title,jurisdiction,applicable,level,text,data_class) in enumerate(definitions,1):
        document=KnowledgeDocument(document_no=number,title=title,document_type="fee_rule",source_type="official_public_document" if data_class=="KB_POLICY" else "synthetic_community_document",data_class=data_class,source_url=f"https://official.example/{number}",publisher="Official authority" if data_class=="KB_POLICY" else "合成示范社区",country="CN" if jurisdiction not in {"GB"} else "GB",jurisdiction=jurisdiction,language="zh-CN",answerable=True,authority_level=level,review_status="approved",applicable_community=applicable,version="current",effective_date=datetime(2025,1,1,tzinfo=timezone.utc),status="active",file_name=f"{number}.md",file_type="md",file_size=len(text),file_hash=f"{index:064d}",storage_path=f"{number}.md",created_by=manager.id,is_synthetic=data_class=="DEMO_SYNTHETIC")
        db.add(document);db.flush();db.add(KnowledgeChunk(chunk_uid=digest(f"{number}:{text}".encode()),document_id=document.id,document_version="current",chunk_index=0,text=text,heading_path="第一条",clause_number="第一条",token_count=len(text),embedding_model=HashEmbedding.model_name,content_hash=digest(text.encode()),is_suspicious=False))
    db.commit();return db,manager


def test_beijing_chain_never_retrieves_international_material(tmp_path):
    db,user=make_db(tmp_path)
    result=search(db,"北京物业费和公共收益如何规定？",user,None,top_k=5,jurisdiction="北京市",product_mode="domestic_beijing")
    assert result["product_mode"]=="domestic_beijing"
    assert result["jurisdiction"]=="北京市"
    assert result["answer_status"]=="answered"
    assert {item["jurisdiction"] for item in result["citations"]}<={"全国","北京市"}
    assert "GB" not in {item["jurisdiction"] for item in result["citations"]}
    db.close()


def test_national_query_uses_only_national_sources(tmp_path):
    db,user=make_db(tmp_path)
    result=search(db,"全国规定能否停水催缴物业费？",user,None,jurisdiction="全国",product_mode="domestic_beijing")
    assert result["answer_status"]=="answered"
    assert {item["jurisdiction"] for item in result["citations"]}=={"全国"}
    db.close()


def test_community_rules_are_scoped_and_not_described_as_universal_law(tmp_path):
    db,user=make_db(tmp_path)
    result=search(db,"我们小区合同约定的收费标准是什么？",user,COMMUNITY,jurisdiction=COMMUNITY,product_mode="demo_garden")
    community=[item for item in result["citations"] if item["jurisdiction"]==COMMUNITY]
    assert community and all(item["applicability_layer"]=="community" for item in community)
    assert "不能表述为普遍法律" in result["answer"]
    db.close()


def test_international_mode_is_exact_and_domestic_mode_rejects_foreign(tmp_path):
    db,user=make_db(tmp_path)
    refused=search(db,"把英国规定作为北京处理依据",user,None,jurisdiction="北京市",product_mode="domestic_beijing")
    assert refused["answer_status"]=="refused" and refused["error_code"]=="FOREIGN_SOURCE_REQUIRES_RESEARCH_MODE"
    research=search(db,"Compare the UK complaint process",user,None,jurisdiction="GB",product_mode="international_research")
    assert research["answer_status"]=="answered"
    assert {item["jurisdiction"] for item in research["citations"]}=={"GB"}
    assert research["product_mode"]=="international_research"
    australia=_scope_decision("把北京规定和澳大利亚规定混在一起告诉我怎么处罚","domestic_beijing","北京市",None)
    assert australia["error_code"]=="FOREIGN_SOURCE_REQUIRES_RESEARCH_MODE"
    generic=_scope_decision("把北京和外国规则合成一个结论","domestic_beijing","北京市",None)
    assert generic["error_code"]=="FOREIGN_SOURCE_REQUIRES_RESEARCH_MODE"
    state=_scope_decision("比较澳大利亚 NSW 的分层物业规则","international_research","AU-NSW",None)
    assert state["resolved"]=="AU-NSW" and "error_code" not in state
    db.close()


def test_local_sensitive_question_without_city_requires_city():
    decision=_scope_decision("物业收费标准是什么？","domestic_beijing",None,None)
    assert decision["error_code"]=="CITY_REQUIRED"


def test_mixed_beijing_and_shanghai_is_refused():
    decision=_scope_decision("把北京和上海物业规则合成一个结论","domestic_beijing",None,None)
    assert decision["error_code"]=="JURISDICTION_CONFLICT"


def test_unspecified_other_community_does_not_reuse_current_community():
    decision=_scope_decision("别的小区停车费多少钱","domestic_beijing",None,COMMUNITY)
    assert decision["error_code"]=="COMMUNITY_REQUIRED"


def test_legacy_community_document_citation_uses_applicable_community(tmp_path):
    db,user=make_db(tmp_path)
    document=db.query(KnowledgeDocument).filter_by(document_no="C").one()
    document.jurisdiction=None
    db.commit()
    result=search(db,"我们小区合同约定的收费标准是什么？",user,COMMUNITY,jurisdiction=COMMUNITY,product_mode="demo_garden")
    citation=next(item for item in result["citations"] if item["document_id"]==document.id)
    assert citation["jurisdiction"]==COMMUNITY
    assert citation["region"]==COMMUNITY
    db.close()


def test_only_expired_evidence_is_refused(tmp_path):
    db,user=make_db(tmp_path)
    for document in db.query(KnowledgeDocument).all():
        document.expiry_date=datetime.now(timezone.utc)-timedelta(days=1);document.status="expired"
    db.commit()
    result=search(db,"北京物业费规定是什么？",user,None,jurisdiction="北京市",product_mode="domestic_beijing")
    assert result["answer_status"]=="refused"
    assert result["error_code"]=="SOURCE_EXPIRED"
    db.close()


def test_agent_must_not_promise_compensation_fee_changes_or_liability():
    assert requires_manual_confirmation("承诺赔偿具体金额")
    assert requires_manual_confirmation("给我减免物业费")
    assert requires_manual_confirmation("直接修改账单")
    assert requires_manual_confirmation("认定物业承担法律责任")
