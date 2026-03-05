"""API 入口 smoke 測試"""


def test_root(client):
    """根路徑回傳 status"""
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health(client):
    """健康檢查"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"
