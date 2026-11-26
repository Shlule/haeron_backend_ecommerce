import gzip
import json

from rest_framework_simplejwt.tokens import RefreshToken

from .test_backoffice import staff  # noqa: F401  (fixture)


def test_responses_are_compressed(client, staff):  # noqa: F811
    token = str(RefreshToken.for_user(staff).access_token)
    response = client.post(
        "/graphql/",
        json.dumps({"query": "{ backoffice { resources } }"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_ACCEPT_ENCODING="gzip",
    )
    assert response.status_code == 200
    assert response["Content-Encoding"] == "gzip"
    body = gzip.decompress(response.content)
    assert "errors" not in json.loads(body)
    assert len(response.content) * 4 < len(body)
