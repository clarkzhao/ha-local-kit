import unittest
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from ha_local_kit.sgcc.collector import AuthHealth, check_page, visit, session_seed, save_session


class AuthTests(unittest.TestCase):
    def page(self, *, loaded=False, health=None):
        page = SimpleNamespace(url='about:blank')
        page.locator = lambda _: SimpleNamespace(inner_text=lambda: '退出 账户余额')
        def goto(url, **kwargs):
            page.url = url
            if health:
                health.observe(SimpleNamespace(url='https://www.95598.cn/api/oauth2/oauth/authorize',
                    status=200, json=lambda: {'code': '20103'}))
        def wait(*args, **kwargs):
            if not loaded:
                raise TimeoutError()
        page.goto, page.wait_for_function = goto, wait
        return page

    def test_stale_logout_label_cannot_hide_authentication_failure(self):
        health = AuthHealth()
        with self.assertRaisesRegex(RuntimeError, 'login_required'):
            visit(self.page(health=health), '/osgweb/my95598', health)

    def test_successful_account_load_overrides_transient_refresh_rejection(self):
        health = AuthHealth()
        visit(self.page(loaded=True, health=health), '/osgweb/my95598', health)

    def test_unknown_loading_failure_is_not_called_expired_login(self):
        with self.assertRaisesRegex(RuntimeError, 'account_unconfirmed'):
            visit(self.page(), '/osgweb/my95598', AuthHealth())

    def test_unrelated_host_cannot_mark_login_expired(self):
        health = AuthHealth()
        health.observe(SimpleNamespace(url='https://example.test/api/auth',status=401))
        self.assertFalse(health.rejected)

    def test_login_redirect_is_explicit(self):
        page = self.page()
        page.url = 'https://www.95598.cn/osgweb/login'
        with self.assertRaisesRegex(RuntimeError, 'login_required'):
            check_page(page)

    def test_session_export_excludes_unrelated_sites(self):
        context = SimpleNamespace(storage_state=lambda **kw: {
            'cookies': [{'domain': '.95598.cn', 'name': 'synthetic', 'value': 'fixture'},
                        {'domain': 'unrelated.example', 'name': 'synthetic', 'value': 'fixture'}],
            'origins': [{'origin': 'https://www.95598.cn', 'localStorage': []},
                        {'origin': 'https://unrelated.example', 'localStorage': []}]})
        page = SimpleNamespace(evaluate=lambda _: {'synthetic_session': 'fixture'})
        with TemporaryDirectory() as temp, patch('ha_local_kit.sgcc.collector.DATA', Path(temp)):
            save_session(context, page)
            state = json.loads((Path(temp)/'session.private.json').read_text())
            self.assertEqual([c['domain'] for c in state['cookies']], ['.95598.cn'])
            self.assertEqual([o['origin'] for o in state['origins']], ['https://www.95598.cn'])

    @unittest.skipUnless(shutil.which('node'), 'Node needed to execute the browser initialization JavaScript')
    def test_navigation_preserves_renewed_session_and_respects_origin(self):
        seed = json.dumps(session_seed({'synthetic_session': 'old'}))
        script = '''
          const assert = require('node:assert/strict');
          global.location = {origin:'https://www.95598.cn'};
          const values = new Map();
          global.sessionStorage = {get length(){return values.size},setItem(k,v){values.set(k,v)}};
          const seed = SEED;
          eval(seed);
          assert.equal(values.get('synthetic_session'),'old');
          values.set('synthetic_session','renewed');
          eval(seed);
          assert.equal(values.get('synthetic_session'),'renewed');
          values.clear(); location.origin='https://unrelated.example';
          eval(seed);
          assert.equal(values.size,0);
        '''.replace('SEED', seed)
        subprocess.run(['node', '-e', script], check=True, capture_output=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
