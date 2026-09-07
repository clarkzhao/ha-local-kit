"""Small Home Assistant CLI for an agent running locally or over SSH.

Uses the local HA API. No listening service is created. A token is supplied through
HA_TOKEN_FILE or the adjacent ha-token file, never a command-line argument.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import tempfile
from urllib import error, parse, request

DEFAULT_URL = 'http://127.0.0.1:8123'
DEFAULT_TOKEN_FILE = Path.home() / '.config/ha-local-kit/ha-token'
ACTIONS = {
    'light': {'turn_on', 'turn_off', 'toggle'},
    'switch': {'turn_on', 'turn_off', 'toggle'},
    'cover': {'open_cover', 'close_cover', 'stop_cover', 'set_cover_position'},
    'climate': {'turn_on', 'turn_off', 'set_temperature', 'set_hvac_mode', 'set_fan_mode'},
    'scene': {'turn_on'},
    'script': {'turn_on', 'turn_off'},
}


class AgentError(Exception):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AgentError('HA returned a redirect; check the configured URL.')


def entity_domain(entity_id):
    if not re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+', entity_id):
        raise AgentError('Invalid entity ID; use an ID returned by entities.')
    return entity_id.split('.', 1)[0]


def make_action(entity_id, action, data):
    domain = entity_domain(entity_id)
    if action not in ACTIONS.get(domain, set()):
        raise AgentError('This action is not supported for the entity domain.')
    if not isinstance(data, dict):
        raise AgentError('--data must be a JSON object.')
    if any(key in data for key in ('entity_id', 'area_id', 'device_id', 'target')):
        raise AgentError('Select the target using the entity argument only.')
    # Reject NaN / Infinity rather than transmitting non-standard JSON.
    try:
        json.dumps(data, allow_nan=False)
    except (TypeError, ValueError):
        raise AgentError('Action data must contain valid JSON values.') from None
    return '/api/services/{}/{}'.format(domain, action), dict(data, entity_id=entity_id)


def compact_state(state):
    return {'entity_id': state.get('entity_id'), 'state': state.get('state'),
            'name': state.get('attributes', {}).get('friendly_name'),
            'last_updated': state.get('last_updated')}


class HAClient:
    def __init__(self, base_url, token_file, timeout=10):
        parsed = parse.urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise AgentError('HA URL must use HTTP or HTTPS.')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise AgentError('HA URL must not include credentials, query or fragment.')
        self.base_url = base_url.rstrip('/')
        self.token_file = Path(token_file).expanduser()
        self.timeout = timeout
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())

    def _token(self):
        try:
            if os.name != 'nt' and self.token_file.stat().st_mode & 0o077:
                raise AgentError('Token file must have permissions 600.')
            token = self.token_file.read_text(encoding='utf-8').strip()
        except OSError:
            raise AgentError('HA token is not configured. Run configure-token in your terminal.') from None
        if not token or any(c.isspace() for c in token):
            raise AgentError('Token file is empty or malformed.')
        return token

    def api(self, method, path, data=None, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self._token()
        body = None if data is None else json.dumps(data, allow_nan=False).encode('utf-8')
        req = request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read()
                if not authenticated:
                    return {'reachable': True, 'http_status': response.status,
                            'api_authorization_checked': False}
        except error.HTTPError as exc:
            suffix = ' No automatic retry was made; check device state before retrying.' if method == 'POST' else ''
            raise AgentError('HA returned HTTP {}.{}'.format(exc.code, suffix)) from None
        except (OSError, error.URLError):
            if method == 'POST':
                raise AgentError('Command outcome is unknown. No automatic retry was made; query state first.') from None
            raise AgentError('Could not reach HA; check the service and URL.') from None
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            raise AgentError('HA returned an unexpected response.') from None

    def entities(self, domain=None):
        states = self.api('GET', '/api/states')
        if not isinstance(states, list):
            raise AgentError('HA returned an unexpected entity list.')
        return [compact_state(s) for s in states if not domain or s.get('entity_id', '').startswith(domain + '.')]

    def state(self, entity_id):
        entity_domain(entity_id)
        return compact_state(self.api('GET', '/api/states/' + entity_id))

    def call(self, entity_id, action, data):
        path, payload = make_action(entity_id, action, data)
        before = self.state(entity_id)
        if before['state'] == 'unavailable' or (before['state'] == 'unknown' and entity_domain(entity_id) != 'scene'):
            raise AgentError('The entity is unavailable or its state is unknown; command not sent.')
        self.api('POST', path, payload)
        result = {'service_call_returned_success': True, 'entity_id': entity_id,
                  'action': action, 'physical_result_verified': False}
        try:
            result['reported_state_after_call'] = self.state(entity_id)
        except AgentError:
            result['state_readback'] = 'failed; service call was not repeated'
        return result


def configure_token(path):
    token = getpass.getpass('Paste a Home Assistant access token (hidden): ').strip()
    if not token or any(c.isspace() for c in token):
        raise AgentError('Token is empty or malformed; nothing saved.')
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.ha-token-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(token + '\n')
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'token_saved': True, 'path': str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('HA_URL', DEFAULT_URL))
    parser.add_argument('--token-file', default=os.environ.get('HA_TOKEN_FILE', str(DEFAULT_TOKEN_FILE)))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('health', help='Check the local web service without credentials.')
    commands.add_parser('configure-token', help='Save an existing HA token using a hidden terminal prompt.')
    entities = commands.add_parser('entities', help='List IDs, names and states.')
    entities.add_argument('--domain', choices=tuple(ACTIONS) + ('sensor', 'binary_sensor'))
    state = commands.add_parser('state')
    state.add_argument('entity')
    call = commands.add_parser('call')
    call.add_argument('action')
    call.add_argument('entity')
    call.add_argument('--data', default='{}')
    call.add_argument('--dry-run', action='store_true', help='Print a request without contacting HA.')
    args = parser.parse_args(argv)
    try:
        client = HAClient(args.url, args.token_file)
        if args.command == 'configure-token':
            result = configure_token(args.token_file)
        elif args.command == 'health':
            result = client.api('GET', '/', authenticated=False)
        elif args.command == 'entities':
            result = client.entities(args.domain)
        elif args.command == 'state':
            result = client.state(args.entity)
        else:
            try:
                data = json.loads(args.data)
            except ValueError:
                raise AgentError('--data must contain valid JSON.') from None
            path, payload = make_action(args.entity, args.action, data)
            result = ({'dry_run': True, 'method': 'POST', 'path': path, 'data': payload}
                      if args.dry_run else client.call(args.entity, args.action, data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except AgentError as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
