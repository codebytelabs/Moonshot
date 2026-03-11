"""
APEX-SWARM Iteration 3 Backend Tests
Tests: health, swarm control, agents/status, TinyClaw proxy, TinyOffice routing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ── Health ───────────────────────────────────────────────────────────────────

class TestHealth:
    """GET /api/health"""

    def test_health_alive(self, client):
        r = client.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "alive"
        assert "swarm_active" in data
        assert "timestamp" in data


# ── Swarm Control ─────────────────────────────────────────────────────────────

class TestSwarmControl:
    """POST /api/swarm/start and /api/swarm/stop"""

    def test_start_swarm(self, client):
        r = client.post(f"{BASE_URL}/api/swarm/start")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("started", "already_running")

    def test_swarm_status_active(self, client):
        # Start first to ensure it's running
        client.post(f"{BASE_URL}/api/swarm/start")
        r = client.get(f"{BASE_URL}/api/swarm/status")
        assert r.status_code == 200
        data = r.json()
        assert data["active"] is True

    def test_stop_swarm(self, client):
        r = client.post(f"{BASE_URL}/api/swarm/stop")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "stopped"

    def test_swarm_status_after_stop(self, client):
        client.post(f"{BASE_URL}/api/swarm/stop")
        r = client.get(f"{BASE_URL}/api/swarm/status")
        assert r.status_code == 200
        data = r.json()
        assert data["active"] is False


# ── Agents Status ─────────────────────────────────────────────────────────────

class TestAgentsStatus:
    """GET /api/agents/status — must return all 5 agents with roles and recent_logs"""

    def test_agents_status_ok(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        assert r.status_code == 200

    def test_agents_status_structure(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        data = r.json()
        assert "agents" in data
        assert "swarm_active" in data
        assert "cycle_count" in data
        assert isinstance(data["cycle_count"], int)

    def test_all_5_agents_present(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        agents = r.json()["agents"]
        expected = {"tinyclaw", "alpha_scanner", "contract_sniper", "execution_core", "quant_mutator"}
        assert expected == set(agents.keys()), f"Missing agents: {expected - set(agents.keys())}"

    def test_tinyclaw_orchestrator_fields(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        tc = r.json()["agents"]["tinyclaw"]
        assert tc["role"] == "Master Orchestrator"
        assert "recent_logs" in tc
        assert isinstance(tc["recent_logs"], list)
        assert "status" in tc
        assert "last_action" in tc

    def test_alpha_scanner_fields(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        agent = r.json()["agents"]["alpha_scanner"]
        assert agent["role"] == "Market Intelligence"
        assert "total_hits" in agent
        assert "recent_logs" in agent

    def test_contract_sniper_fields(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        agent = r.json()["agents"]["contract_sniper"]
        assert agent["role"] == "Security Auditor"
        assert "total_blocked" in agent
        assert "recent_logs" in agent

    def test_execution_core_fields(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        agent = r.json()["agents"]["execution_core"]
        assert agent["role"] == "Trade Executor"
        assert "total_trades" in agent
        assert "recent_logs" in agent

    def test_quant_mutator_fields(self, client):
        r = client.get(f"{BASE_URL}/api/agents/status")
        agent = r.json()["agents"]["quant_mutator"]
        assert agent["role"] == "Strategy Optimizer"
        assert "total_mutations" in agent
        assert "recent_logs" in agent


# ── TinyClaw API Proxy ────────────────────────────────────────────────────────

class TestTinyclawProxy:
    """GET /api/tc/agents and /api/tc/teams — proxy to port 3777"""

    def test_tc_agents_ok(self, client):
        r = client.get(f"{BASE_URL}/api/tc/agents")
        assert r.status_code == 200

    def test_tc_agents_4_apex_agents(self, client):
        r = client.get(f"{BASE_URL}/api/tc/agents")
        data = r.json()
        expected = {"alpha_scanner", "contract_sniper", "execution_core", "quant_mutator"}
        assert expected == set(data.keys()), f"Missing TC agents: {expected - set(data.keys())}"

    def test_tc_agents_have_name_and_model(self, client):
        r = client.get(f"{BASE_URL}/api/tc/agents")
        for agent_id, agent_data in r.json().items():
            assert "name" in agent_data, f"{agent_id} missing 'name'"
            assert "model" in agent_data, f"{agent_id} missing 'model'"

    def test_tc_teams_ok(self, client):
        r = client.get(f"{BASE_URL}/api/tc/teams")
        assert r.status_code == 200

    def test_tc_teams_apex_swarm_present(self, client):
        r = client.get(f"{BASE_URL}/api/tc/teams")
        data = r.json()
        assert "apex_swarm" in data, f"apex_swarm team not found: {list(data.keys())}"

    def test_tc_teams_apex_swarm_agents(self, client):
        r = client.get(f"{BASE_URL}/api/tc/teams")
        team = r.json()["apex_swarm"]
        assert "agents" in team
        assert len(team["agents"]) == 4
        expected = {"alpha_scanner", "contract_sniper", "execution_core", "quant_mutator"}
        assert expected == set(team["agents"])

    def test_tc_agents_not_tinyclaw_orchestrator(self, client):
        """TinyClaw itself (orchestrator) should NOT be in the TC agents list"""
        r = client.get(f"{BASE_URL}/api/tc/agents")
        assert "tinyclaw" not in r.json()


# ── Dashboard and other endpoints ─────────────────────────────────────────────

class TestOtherEndpoints:
    """Quick smoke tests for remaining endpoints"""

    def test_dashboard(self, client):
        r = client.get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "portfolio_value" in data
        assert "swarm_active" in data

    def test_positions(self, client):
        r = client.get(f"{BASE_URL}/api/positions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_agent_logs(self, client):
        r = client.get(f"{BASE_URL}/api/agent-logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
