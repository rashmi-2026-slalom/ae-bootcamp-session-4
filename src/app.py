"""
Slalom Capabilities Management System API

A FastAPI application that enables Slalom consultants to register their
capabilities and manage consulting expertise across the organization.
"""

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any

from pydantic import BaseModel, Field

app = FastAPI(title="Slalom Capabilities Management API",
              description="API for managing consulting capabilities and consultant expertise")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

practice_leads_file = current_dir / "practice_leads.json"
audit_log_file = current_dir / "audit.log"
session_ttl_minutes = 120


class LoginRequest(BaseModel):
    username: str
    password: str


class CapacityUpdateRequest(BaseModel):
    capacity: int = Field(ge=0)


def password_hash(password: str, salt: str | None = None) -> str:
    """Create a salted password hash suitable for file storage."""
    use_salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{use_salt}:{password}".encode("utf-8")).hexdigest()
    return f"{use_salt}${digest}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        salt, known_hash = encoded_hash.split("$", maxsplit=1)
    except ValueError:
        return False

    candidate_hash = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate_hash, known_hash)


def create_default_practice_leads() -> list[dict[str, Any]]:
    return [
        {
            "username": "alex.practicelead",
            "password_hash": password_hash("SlalomLead!2026"),
            "role": "practice_lead",
            "practice_areas": ["Technology", "Strategy", "Operations"],
            "approval_workflow": "required",
        }
    ]


def load_practice_leads() -> list[dict[str, Any]]:
    if not practice_leads_file.exists():
        default_leads = create_default_practice_leads()
        practice_leads_file.write_text(json.dumps(default_leads, indent=2), encoding="utf-8")
        return default_leads

    with practice_leads_file.open("r", encoding="utf-8") as file:
        leads: list[dict[str, Any]] = json.load(file)

    # Backfill hashes if a plaintext password ever exists in the file.
    changed = False
    for lead in leads:
        if "password_hash" not in lead and "password" in lead:
            lead["password_hash"] = password_hash(lead["password"])
            lead.pop("password", None)
            changed = True

    if changed:
        practice_leads_file.write_text(json.dumps(leads, indent=2), encoding="utf-8")

    return leads


def write_audit_event(action: str, actor: str, details: dict[str, Any]) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "details": details,
    }
    with audit_log_file.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event) + "\n")


practice_leads = load_practice_leads()
active_sessions: dict[str, dict[str, Any]] = {}
registration_requests: list[dict[str, Any]] = []
next_request_id = 1

# In-memory capabilities database
capabilities = {
    "Cloud Architecture": {
        "description": "Design and implement scalable cloud solutions using AWS, Azure, and GCP",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["AWS Solutions Architect", "Azure Architect Expert"],
        "industry_verticals": ["Healthcare", "Financial Services", "Retail"],
        "capacity": 40,  # hours per week available across team
        "consultants": ["alice.smith@slalom.com", "bob.johnson@slalom.com"]
    },
    "Data Analytics": {
        "description": "Advanced data analysis, visualization, and machine learning solutions",
        "practice_area": "Technology", 
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Tableau Desktop Specialist", "Power BI Expert", "Google Analytics"],
        "industry_verticals": ["Retail", "Healthcare", "Manufacturing"],
        "capacity": 35,
        "consultants": ["emma.davis@slalom.com", "sophia.wilson@slalom.com"]
    },
    "DevOps Engineering": {
        "description": "CI/CD pipeline design, infrastructure automation, and containerization",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"], 
        "certifications": ["Docker Certified Associate", "Kubernetes Admin", "Jenkins Certified"],
        "industry_verticals": ["Technology", "Financial Services"],
        "capacity": 30,
        "consultants": ["john.brown@slalom.com", "olivia.taylor@slalom.com"]
    },
    "Digital Strategy": {
        "description": "Digital transformation planning and strategic technology roadmaps",
        "practice_area": "Strategy",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Digital Transformation Certificate", "Agile Certified Practitioner"],
        "industry_verticals": ["Healthcare", "Financial Services", "Government"],
        "capacity": 25,
        "consultants": ["liam.anderson@slalom.com", "noah.martinez@slalom.com"]
    },
    "Change Management": {
        "description": "Organizational change leadership and adoption strategies",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Prosci Certified", "Lean Six Sigma Black Belt"],
        "industry_verticals": ["Healthcare", "Manufacturing", "Government"],
        "capacity": 20,
        "consultants": ["ava.garcia@slalom.com", "mia.rodriguez@slalom.com"]
    },
    "UX/UI Design": {
        "description": "User experience design and digital product innovation",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Adobe Certified Expert", "Google UX Design Certificate"],
        "industry_verticals": ["Retail", "Healthcare", "Technology"],
        "capacity": 30,
        "consultants": ["amelia.lee@slalom.com", "harper.white@slalom.com"]
    },
    "Cybersecurity": {
        "description": "Information security strategy, risk assessment, and compliance",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["CISSP", "CISM", "CompTIA Security+"],
        "industry_verticals": ["Financial Services", "Healthcare", "Government"],
        "capacity": 25,
        "consultants": ["ella.clark@slalom.com", "scarlett.lewis@slalom.com"]
    },
    "Business Intelligence": {
        "description": "Enterprise reporting, data warehousing, and business analytics",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Microsoft BI Certification", "Qlik Sense Certified"],
        "industry_verticals": ["Retail", "Manufacturing", "Financial Services"],
        "capacity": 35,
        "consultants": ["james.walker@slalom.com", "benjamin.hall@slalom.com"]
    },
    "Agile Coaching": {
        "description": "Agile transformation and team coaching for scaled delivery",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Certified Scrum Master", "SAFe Agilist", "ICAgile Certified"],
        "industry_verticals": ["Technology", "Financial Services", "Healthcare"],
        "capacity": 20,
        "consultants": ["charlotte.young@slalom.com", "henry.king@slalom.com"]
    }
}


def get_session(x_session_token: str | None) -> dict[str, Any] | None:
    if not x_session_token:
        return None

    session = active_sessions.get(x_session_token)
    if not session:
        return None

    if datetime.now(timezone.utc) > session["expires_at"]:
        active_sessions.pop(x_session_token, None)
        return None

    return session


def require_practice_lead(x_session_token: str | None) -> dict[str, Any]:
    session = get_session(x_session_token)
    if not session or session.get("role") != "practice_lead":
        raise HTTPException(status_code=403, detail="Practice lead access required")
    return session


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/capabilities")
def get_capabilities(practice_area: str | None = None, search: str | None = None):
    filtered_capabilities = capabilities

    if practice_area:
        expected_area = practice_area.strip().lower()
        filtered_capabilities = {
            name: details
            for name, details in filtered_capabilities.items()
            if details.get("practice_area", "").lower() == expected_area
        }

    if search:
        query = search.strip().lower()
        filtered_capabilities = {
            name: details
            for name, details in filtered_capabilities.items()
            if query in name.lower()
            or query in details.get("description", "").lower()
            or query in details.get("practice_area", "").lower()
        }

    return filtered_capabilities


@app.post("/auth/login")
def login(payload: LoginRequest):
    for lead in practice_leads:
        if lead["username"] == payload.username and verify_password(payload.password, lead["password_hash"]):
            token = secrets.token_urlsafe(32)
            active_sessions[token] = {
                "username": lead["username"],
                "role": lead["role"],
                "practice_areas": lead.get("practice_areas", []),
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=session_ttl_minutes),
            }
            write_audit_event("login", lead["username"], {"status": "success"})
            return {
                "token": token,
                "user": {
                    "username": lead["username"],
                    "role": lead["role"],
                    "practice_areas": lead.get("practice_areas", []),
                },
                "expires_in_minutes": session_ttl_minutes,
            }

    write_audit_event("login", payload.username, {"status": "failed"})
    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.get("/auth/me")
def auth_me(x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
    session = get_session(x_session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "username": session["username"],
        "role": session["role"],
        "practice_areas": session.get("practice_areas", []),
        "expires_at": session["expires_at"].isoformat(),
    }


@app.post("/auth/logout")
def logout(x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
    session = get_session(x_session_token)
    if x_session_token:
        active_sessions.pop(x_session_token, None)

    if session:
        write_audit_event("logout", session["username"], {"status": "success"})
    return {"message": "Logged out"}


@app.post("/capabilities/{capability_name}/register")
def register_for_capability(
    capability_name: str,
    email: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    """Register a consultant or create an approval request."""
    global next_request_id

    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is not already registered
    if email in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is already registered for this capability"
        )

    session = get_session(x_session_token)
    if session and session.get("role") == "practice_lead":
        capability["consultants"].append(email)
        write_audit_event(
            "register_consultant",
            session["username"],
            {"capability": capability_name, "email": email, "mode": "direct"},
        )
        return {"message": f"Registered {email} for {capability_name}", "status": "approved"}

    duplicate_request = any(
        request["capability"] == capability_name
        and request["email"] == email
        and request["status"] == "pending"
        for request in registration_requests
    )
    if duplicate_request:
        raise HTTPException(status_code=400, detail="A pending request already exists")

    new_request = {
        "id": next_request_id,
        "capability": capability_name,
        "email": email,
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    next_request_id += 1
    registration_requests.append(new_request)
    write_audit_event("register_request", email, {"capability": capability_name, "request_id": new_request["id"]})
    return {
        "message": f"Registration request submitted for {email}",
        "status": "pending",
        "request": new_request,
    }


@app.delete("/capabilities/{capability_name}/unregister")
def unregister_from_capability(
    capability_name: str,
    email: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    """Unregister a consultant from a capability"""
    session = require_practice_lead(x_session_token)

    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is registered
    if email not in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is not registered for this capability"
        )

    # Remove consultant
    capability["consultants"].remove(email)
    write_audit_event(
        "unregister_consultant",
        session["username"],
        {"capability": capability_name, "email": email},
    )
    return {"message": f"Unregistered {email} from {capability_name}"}


@app.get("/registration-requests")
def get_registration_requests(
    status: str = "pending",
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    require_practice_lead(x_session_token)
    return [request for request in registration_requests if request["status"] == status]


@app.post("/registration-requests/{request_id}/approve")
def approve_registration_request(
    request_id: int,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    session = require_practice_lead(x_session_token)
    request = next((item for item in registration_requests if item["id"] == request_id), None)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")

    capability = capabilities.get(request["capability"])
    if not capability:
        raise HTTPException(status_code=404, detail="Capability not found")

    if request["email"] not in capability["consultants"]:
        capability["consultants"].append(request["email"])

    request["status"] = "approved"
    request["reviewed_by"] = session["username"]
    request["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    write_audit_event(
        "approve_registration_request",
        session["username"],
        {"request_id": request_id, "capability": request["capability"], "email": request["email"]},
    )

    return {"message": "Request approved", "request": request}


@app.post("/registration-requests/{request_id}/reject")
def reject_registration_request(
    request_id: int,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    session = require_practice_lead(x_session_token)
    request = next((item for item in registration_requests if item["id"] == request_id), None)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")

    request["status"] = "rejected"
    request["reviewed_by"] = session["username"]
    request["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    write_audit_event(
        "reject_registration_request",
        session["username"],
        {"request_id": request_id, "capability": request["capability"], "email": request["email"]},
    )

    return {"message": "Request rejected", "request": request}


@app.get("/consultants/{email}/registrations")
def get_consultant_registrations(email: str):
    registered_for = []
    for capability_name, details in capabilities.items():
        if email in details.get("consultants", []):
            registered_for.append(capability_name)
    return {"email": email, "capabilities": registered_for}


@app.put("/capabilities/{capability_name}/capacity")
def update_capability_capacity(
    capability_name: str,
    payload: CapacityUpdateRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    session = require_practice_lead(x_session_token)
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    capabilities[capability_name]["capacity"] = payload.capacity
    write_audit_event(
        "update_capacity",
        session["username"],
        {"capability": capability_name, "capacity": payload.capacity},
    )
    return {"message": f"Updated capacity for {capability_name}", "capacity": payload.capacity}


@app.get("/audit-logs")
def get_audit_logs(x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
    require_practice_lead(x_session_token)
    if not audit_log_file.exists():
        return []

    with audit_log_file.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    logs = []
    for line in lines[-200:]:
        try:
            logs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return logs
