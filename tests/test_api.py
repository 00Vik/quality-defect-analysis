import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

def test_clean_data():
    response = client.get("/clean_data")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_records" in stats

def test_defect_by_id():
    # 先获取一个存在的 defect_id
    resp = client.get("/clean_data")
    if resp.json():
        first_id = resp.json()[0].get("defect_id")
        response = client.get(f"/defect/{first_id}")
        assert response.status_code == 200
        assert response.json().get("defect_id") == first_id
    else:
        pytest.skip("No data available")

def test_defect_not_found():
    response = client.get("/defect/999999")
    assert response.status_code == 200  # FastAPI 返回 JSON，状态码仍是 200
    assert "error" in response.json()