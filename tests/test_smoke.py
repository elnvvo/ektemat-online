def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
