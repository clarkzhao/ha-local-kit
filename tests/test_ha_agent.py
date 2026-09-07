import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ha_local_kit import agent as ha

class MockHA(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        self.server.requests.append(('GET', self.path, self.headers.get('Authorization')))
        if self.server.redirect:
            self.send_response(302)
            self.send_header('Location', self.server.redirect)
            self.end_headers()
        elif self.path.startswith('/api/states/'):
            self.send_json(200, {'entity_id': 'light.test', 'state': self.server.state, 'attributes': {}})
        else:
            self.send_json(200, [])

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(('POST', self.path, payload))
        if self.server.fail_post:
            self.send_json(500, {})
        else:
            self.server.state = 'on'
            self.send_json(200, [])


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        token_file = Path(self.tmp.name) / 'ha-token'
        token_file.write_text('FAKE_TEST_TOKEN')
        token_file.chmod(0o600)
        self.server = HTTPServer(('127.0.0.1', 0), MockHA)
        self.server.requests = []
        self.server.state = 'off'
        self.server.fail_post = False
        self.server.redirect = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = ha.HAClient('http://127.0.0.1:' + str(self.server.server_port), token_file)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_single_service_call_and_state_readback(self):
        result = self.client.call('light.test', 'turn_on', {'brightness': 90})
        self.assertEqual(result['reported_state_after_call']['state'], 'on')
        self.assertFalse(result['physical_result_verified'])
        posts = [r for r in self.server.requests if r[0] == 'POST']
        self.assertEqual(posts, [('POST', '/api/services/light/turn_on', {'brightness': 90, 'entity_id': 'light.test'})])
        self.assertEqual(self.server.requests[0][2], 'Bearer FAKE_TEST_TOKEN')

    def test_failed_post_is_not_retried(self):
        self.server.fail_post = True
        with self.assertRaisesRegex(ha.AgentError, 'No automatic retry'):
            self.client.call('light.test', 'turn_on', {})
        self.assertEqual(sum(r[0] == 'POST' for r in self.server.requests), 1)

    def test_unavailable_entity_does_not_send_command(self):
        self.server.state = 'unavailable'
        with self.assertRaises(ha.AgentError):
            self.client.call('light.test', 'turn_on', {})
        self.assertFalse(any(r[0] == 'POST' for r in self.server.requests))

    def test_scene_can_run_before_its_first_activation(self):
        self.server.state = 'unknown'
        result = self.client.call('scene.test', 'turn_on', {})
        self.assertTrue(result['service_call_returned_success'])
        self.assertEqual(sum(r[0] == 'POST' for r in self.server.requests), 1)

    def test_redirect_is_not_followed_with_credentials(self):
        self.server.redirect = '/unexpected'
        with self.assertRaisesRegex(ha.AgentError, 'redirect'):
            self.client.state('light.test')
        self.assertEqual(len(self.server.requests), 1)

    def test_target_override_and_unsupported_action_rejected_before_network(self):
        for target, action, data in [('light.test', 'turn_on', {'entity_id': 'all'}),
                                     ('lock.test', 'unlock', {}),
                                     ('light.test/other', 'turn_on', {})]:
            with self.assertRaises(ha.AgentError):
                self.client.call(target, action, data)
        self.assertEqual(self.server.requests, [])

    def test_missing_token_does_not_contact_server(self):
        self.client.token_file = Path(self.tmp.name) / 'missing'
        with self.assertRaisesRegex(ha.AgentError, 'not configured'):
            self.client.state('light.test')
        self.assertEqual(self.server.requests, [])

    @unittest.skipIf(ha.os.name == 'nt', 'POSIX file permissions are checked on the Mac')
    def test_token_with_group_access_is_not_used(self):
        self.client.token_file.chmod(0o640)
        with self.assertRaisesRegex(ha.AgentError, 'permissions 600'):
            self.client.state('light.test')
        self.assertEqual(self.server.requests, [])


if __name__ == '__main__':
    unittest.main()
