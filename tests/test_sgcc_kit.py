import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from ha_local_kit.sgcc.page_data import daily_rows, monthly_summary, number
from ha_local_kit.sgcc.collector import account
from ha_local_kit.sgcc.snapshot import read


class BillingTests(unittest.TestCase):
    def test_invalid_readings_are_not_free_electricity(self):
        for v in (None, True, 'NaN', 'infinity', ''):
            self.assertIsNone(number(v))
        self.assertEqual(number('0'), 0)
        self.assertEqual(number('1,234.5'), 1234.5)

    def test_daily_rejects_dates_and_preserves_unknown_tou(self):
        rows = daily_rows([{'data':{'tableData':[
            {'day':'2024-01-06','dayElePq':'12.34','thisVPq':0},
            {'day':'2024-01-05','dayElePq':None},
            {'day':'2026-02-30','dayElePq':25}]}}])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['valley_usage'],0)
        self.assertIsNone(rows[0]['flat_usage'])

    def test_bill_has_real_period_and_complete_amount(self):
        result = monthly_summary([{'data':{'powerData':{
            'dataInfo':{'year':2026,'totalEleNum':'120','totalEleCost':0},
            'mothEleList':[
                {'month':'202608','monthEleNum':120,'monthEleCost':0},
                {'month':'202609','monthEleNum':10},
                {'month':'202613','monthEleNum':20,'monthEleCost':20}]}}}])
        self.assertEqual(len(result['months']),1)
        self.assertEqual(result['months'][0]['month'],'2026-08')
        self.assertEqual(result['months'][0]['total_charge'],0)
        with self.assertRaisesRegex(RuntimeError,'data_incomplete'):
            monthly_summary([])

    def test_account_change_is_detectable_without_publishing_id(self):
        self.assertEqual(account('用电户号：12345678901'),account('用电户号: 12345678901'))
        self.assertNotEqual(account('用电户号:12345678901'),account('用电户号:12345678902'))

    def test_stale_value_remains_with_original_date(self):
        with TemporaryDirectory() as temp:
            p=Path(temp)/'snapshot.json'
            p.write_text(json.dumps(dict(status='ok', fetched_at='2020-01-01T00:00:00+08:00',daily_usage=12.34)))
            result=read(p)
            self.assertEqual(result['status'],'stale')
            self.assertEqual(result['daily_usage'],12.34)
            self.assertEqual(result['fetched_at'],'2020-01-01T00:00:00+08:00')


if __name__ == '__main__':
    unittest.main()
