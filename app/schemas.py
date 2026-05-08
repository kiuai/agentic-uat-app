from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    user_id: str
    email: Optional[str] = None
    password: str
    roles: List[str] = []

class UserOut(BaseModel):
    id: int
    user_id: str
    email: Optional[str] = None
    roles: List[str] = []

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectOut(ProjectCreate):
    id: int

class ApplicationCreate(BaseModel):
    project_id: int
    name: str
    base_url: str
    environment: str = "non-prod"

class ApplicationOut(ApplicationCreate):
    id: int

class RequirementIn(BaseModel):
    req_id: str
    text: str
    priority: Optional[str] = None
    risk: Optional[str] = None
    source: Optional[str] = None

class RequirementOut(RequirementIn):
    id: int
    project_id: int
    version: int
    status: str

class Step(BaseModel):
    index: int
    action: str
    selector: Optional[Dict[str, Any]] = None
    input: Optional[str] = None
    expect: Optional[str] = None
    critical: bool = False

class TestCase(BaseModel):
    test_id: str
    title: str
    objective: str
    preconditions: List[str] = []
    data: Dict[str, Any] = {}
    risk: Optional[str] = None
    steps: List[Step]
    requirement_ids: List[str] = []

class BundleOut(BaseModel):
    id: int
    project_id: int
    version_hash: str
    status: str

class RunOut(BaseModel):
    id: int
    bundle_id: int
    status: str
