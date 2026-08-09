from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class LoginIn(BaseModel): username:str; password:str
class WorkOrderIn(BaseModel):
 property_id:str; original_description:str; summary:str; category:str; location_description:str; fault_description:str
 subcategory:str|None=None; equipment_name:str|None=None; equipment_id:str|None=None; impact_scope:str="single"; risk_level:str="low"; priority:str="P3"; contact_phone_masked:str="138****0000"
class AssignIn(BaseModel): assignee_id:str; note:str=""
class TransitionIn(BaseModel): target_status:str; note:str=""; resolution:str|None=None
class RatingIn(BaseModel): score:int=Field(ge=1,le=5); comment:str|None=None
class AnnouncementIn(BaseModel):
 title:str; announcement_type:str; content:str; affected_scope:str; contact_information:str; publisher_unit:str="示例家园物业服务中心"
 start_time:datetime|None=None; end_time:datetime|None=None
 target_type:str="all"; target_building_no:str|None=None; summary:str|None=None; suggested_publish_time:datetime|None=None; scheduled_publish_at:datetime|None=None
class ReviewIn(BaseModel): reason:str
class HandleReviewIn(BaseModel): result:str
class InspectionTaskIn(BaseModel): area_type:str; location_description:str; scheduled_at:datetime; assignee_id:str
class InspectionRecordIn(BaseModel): description:str; abnormal:bool; risk_level:str="low"; attachment_path:str|None=None
class RectificationIn(BaseModel): inspection_record_id:str; description:str; risk_level:str; deadline:datetime; equipment_id:str|None=None
class ApprovalIn(BaseModel): decision:str="approved"; review_comment:str|None=None
class InspectionPlanIn(BaseModel):
 name:str; category:str; target_type:str; target_id:str|None=None; frequency:str; assignee_id:str|None=None; next_run_at:datetime
class EquipmentIn(BaseModel):
 equipment_code:str; name:str; category:str; location:str; property_id:str|None=None; manufacturer:str|None=None; model:str|None=None; installed_at:datetime|None=None; status:str="normal"; next_inspection_at:datetime|None=None
