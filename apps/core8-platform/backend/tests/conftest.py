import os
import sys
import tempfile

# Must be set before config/database are imported.
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "bootstrap.db")
os.environ["DEV_MODE"] = "true"
os.environ["BIND_HOST"] = "127.0.0.1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "core8-test.db"))
    with TestClient(main.app) as c:
        yield c


class Api:
    """Small helper around TestClient with per-user auth headers."""

    def __init__(self, client: TestClient):
        self.c = client
        r = client.post("/api/auth/setup", json={"email": "admin@core8.test", "password": "admin-pass-123"})
        assert r.status_code == 200, r.text
        self.admin = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def user(self, email: str) -> dict:
        r = self.c.post("/api/auth/register", json={"email": email, "password": "user-pass-123"}, headers=self.admin)
        assert r.status_code == 200, r.text
        r = self.c.post("/api/auth/login", json={"email": email, "password": "user-pass-123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def tenant(self, name: str, owner_email: str | None = None) -> str:
        r = self.c.post("/api/tenants", json={"name": name, "owner_email": owner_email}, headers=self.admin)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def assessment(self, tid: str, h: dict) -> str:
        r = self.c.post(f"/api/tenants/{tid}/assessments", headers=h)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def answer(self, tid: str, aid: str, answers: dict, h: dict, expect: int = 200):
        r = self.c.put(f"/api/tenants/{tid}/assessments/{aid}/answers", json={"answers": answers}, headers=h)
        assert r.status_code == expect, r.text
        return r.json()


@pytest.fixture
def api(client):
    return Api(client)


INTAKE = {
    "exec.company_name": "Acme Dental Clinics",
    "exec.industry": "Healthcare services",
    "exec.employee_count": 40,
    "exec.products_services": "Dental check-ups, orthodontics, whitening",
    "exec.customer_types": "Families and young professionals",
    "exec.decision_maker_role": "Managing director",
    "exec.software_stack": ["Google Workspace", "WhatsApp Business", "Excel"],
    "exec.top_pains": ["Leads wait too long for a reply", "Too much paperwork", "Quarterly board strategy unclear"],
    "exec.repetitive_processes": ["Appointment reminders", "Insurance forms", "Lead follow-up"],
    "exec.goals": ["Grow new patients 20%", "Cut admin time"],
    "exec.never_without_approval": ["Sending price quotes", "Refunds"],
    "exec.sensitive_data_categories": ["none"],
    "exec.focus_areas": ["sales_crm", "office_admin", "customer_service"],
}

SALES = {
    "sales_crm.data_sensitivity": "internal",
    "sales_crm.current_workflow": "Leads arrive by WhatsApp and web form; receptionist copies into Excel and calls back.",
    "sales_crm.systems_used": ["WhatsApp Business", "Excel"],
    "sales_crm.monthly_volume": 300,
    "sales_crm.hours_per_week": 20,
    "sales_crm.bottlenecks": ["Slow lead follow-up", "Leads lost in spreadsheets"],
    "sales_crm.business_impact": "high",
    "sales_crm.desired_outcome": "Every lead answered within 5 minutes",
    "sales_crm.lead_sources": ["Website form", "WhatsApp", "Google Ads"],
}

OFFICE = {
    "office_admin.data_sensitivity": "confidential",
    "office_admin.current_workflow": "Staff fill insurance forms by hand and scan them.",
    "office_admin.bottlenecks": ["Manual insurance form filling"],
    "office_admin.business_impact": "medium",
    "office_admin.desired_outcome": "Forms pre-filled automatically",
    "office_admin.admin_tasks": ["Insurance forms", "Supplier invoices filing"],
}

SERVICE = {
    "customer_service.data_sensitivity": "internal",
    "customer_service.current_workflow": "Patients message on WhatsApp; front desk answers between appointments.",
    "customer_service.bottlenecks": ["Unanswered WhatsApp messages after hours"],
    "customer_service.business_impact": "high",
    "customer_service.desired_outcome": "Instant answers to common questions",
    "customer_service.channels": ["whatsapp", "phone"],
    "customer_service.top_request_types": ["Opening hours", "Rescheduling"],
}
