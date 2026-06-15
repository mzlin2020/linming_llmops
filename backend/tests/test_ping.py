def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["code"] == 200
    assert body["data"] == "pong"
