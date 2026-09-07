import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('narwal_helper',Path(__file__).resolve().parents[1]/'extras/narwal/account_helper.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class NarwalTests(unittest.TestCase):
    def test_minimal_identity_omits_serial_and_auth_material(self):
        data={'deviceId':'demo-device','productKey':'demo-product','SN':'demo-serial','token':'demo-token','mobile':'demo-mobile'}
        self.assertEqual(helper.identifiers(data),[{'deviceId':'demo-device','productKey':'demo-product'}])

    def test_known_sensitive_values_are_redacted_from_errors(self):
        result=helper.error_info({'msg':'login failed for demo-phone / demo-code'},('demo-phone','demo-code'))
        self.assertNotIn('demo-phone',result['message'])
        self.assertNotIn('demo-code',result['message'])


if __name__=='__main__':unittest.main()
