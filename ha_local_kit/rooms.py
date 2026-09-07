"""Explicit room mapping → native HA cards; no registry mutation or name guessing."""
import argparse
import json
from pathlib import Path
import re


def build(config):
    path=config.get('dashboard_path','home-rooms')
    if not re.fullmatch(r'[a-z][a-z0-9_-]*',path):
        raise ValueError('Invalid dashboard path')
    sections=[];views=[];ids=set();entities=set()
    for room in config['rooms']:
        rid=room['id']
        if not re.fullmatch(r'[a-z][a-z0-9_-]*',rid) or rid=='overview' or rid in ids:
            raise ValueError('Invalid or duplicate room ID')
        ids.add(rid)
        heading=dict(type='heading',heading=room['name'],heading_style='title',
            icon=room.get('icon','mdi:floor-plan'),tap_action=dict(action='navigate',navigation_path=f'/{path}/{rid}'))
        cards=[]
        for item in room['entities']:
            eid=item['entity_id']
            if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',eid) or eid in entities:
                raise ValueError('Invalid or duplicate entity ID')
            entities.add(eid)
            actions=dict(action='more-info')
            card=dict(type='tile',entity=eid,name=item.get('name',eid),
                tap_action=actions,icon_tap_action=actions)
            if item.get('quick_toggle') and not item.get('protected') and eid.split('.')[0] in ('light','switch'):
                card['icon_tap_action']=dict(action='toggle')
            if item.get('features'):
                card['features']=item['features']
            cards.append(card)
        sections.append(dict(type='grid',cards=[heading,*cards]))
        views.append(dict(title=room['name'],path=rid,type='sections',max_columns=2,
            subview=True,back_path=f'/{path}/overview',sections=[dict(type='grid',cards=cards)]))
    return dict(title=config.get('title','房间看板'),views=[dict(title='全屋',path='overview',type='sections',max_columns=3,sections=sections),*views])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    args=parser.parse_args()
    print(json.dumps(build(json.loads(args.config.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
