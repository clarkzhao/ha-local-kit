import unittest
from ha_local_kit.rooms import build
from ha_local_kit.sgcc.dashboard import build_view,build_detail_views,metric_actions


class DashboardTests(unittest.TestCase):
    def test_room_controls_require_explicit_opt_in(self):
        result=build({'rooms':[{'id':'demo','name':'Demo','entities':[
            {'entity_id':'light.demo','quick_toggle':True},
            {'entity_id':'switch.demo','quick_toggle':True,'protected':True}]}]})
        cards=result['views'][1]['sections'][0]['cards']
        self.assertEqual(cards[0]['icon_tap_action']['action'],'toggle')
        self.assertEqual(cards[1]['icon_tap_action']['action'],'more-info')

    def test_unknown_or_duplicate_mapping_is_rejected(self):
        for rid in ['../bad','overview']:
            with self.assertRaises(ValueError):build({'rooms':[{'id':rid,'name':'bad','entities':[]}]})
        with self.assertRaises(ValueError):
            build({'rooms':[{'id':'demo','name':'Demo','entities':[{'entity_id':'light.a'},{'entity_id':'light.a'}]}]})

    def test_billing_navigation_uses_source_periods(self):
        paths={v['path'] for v in build_detail_views()}
        for key in ['daily','month_charge','year_usage','due']:
            actions=metric_actions(key)
            self.assertEqual(actions['tap_action'],actions['icon_tap_action'])
            self.assertIn(actions['tap_action']['navigation_path'].split('/')[-1],paths)
        daily=build_view()['sections'][1]['cards'][0]
        self.assertEqual(daily['graph_span'],'31d')
        self.assertTrue(all(s['extend_to'] is False for s in daily['series']))
        self.assertTrue(all('r.date' in s['data_generator'] for s in daily['series']))


if __name__=='__main__':unittest.main()
