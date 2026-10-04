"""Probe token UI/authentication inside a disposable exact application image.

Uses a fresh temporary SQLite database, synthetic identities and no real tokens.
Run via the retained image's interpreter; never against a staging database.
"""
from datetime import timedelta
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from sqlalchemy import select
from mldsafail.web.app import create_app
from mldsafail.web.db import get_session
from mldsafail.web.models import Base, User, utcnow
from mldsafail.web.services import create_api_token


def run():
    with TemporaryDirectory(prefix='token-ui-probe-') as directory:
        app = create_app(config_name='test', config={'DATABASE_URL': 'sqlite:///' + str(Path(directory) / 'test.db')})
        Base.metadata.create_all(app.extensions['mldsafail_engine'])
        client = app.test_client()
        assert client.post('/auth/dev-login').status_code == 302
        now = utcnow()
        plaintext = {}
        with app.app_context():
            database = get_session()
            user = database.scalar(select(User))
            for name, expiry, revoked in [('expired', now - timedelta(days=1), False), ('future', now + timedelta(days=1), False), ('unlimited', None, False), ('revoked-expired', now - timedelta(days=1), True)]:
                token, plaintext[name] = create_api_token(database, user, name, expires_at=expiry)
                if revoked:
                    token.revoked_at = now
                    database.commit()
        response = client.get('/tokens')
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        for name, status in [('expired', 'Expired'), ('future', 'Active'), ('unlimited', 'Active'), ('revoked-expired', 'Revoked')]:
            row = next(row for row in re.findall(r'<tr>(.*?)</tr>', page, re.S) if '<td>' + name + '</td>' in row)
            assert '<td>' + status + '</td>' in row
            assert plaintext[name] not in page
            expected = 401 if name in ('expired', 'revoked-expired') else 200
            assert client.get('/api/v1/me', headers={'Authorization': 'Bearer ' + plaintext[name]}).status_code == expected
        app.extensions['mldsafail_engine'].dispose()
    return {'passed': True, 'token_statuses': ['Expired', 'Active', 'Revoked'], 'expired_authentication_rejected': True, 'synthetic_tokens_not_exposed': True, 'scope': 'native retained application image, disposable SQLite/synthetic browser identity'}


if __name__ == '__main__':
    print(json.dumps(run()))
