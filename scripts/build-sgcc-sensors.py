"""Generate native command_line sensors; copy snapshot.py alongside snapshot.json."""
import argparse
import json
import re

parser=argparse.ArgumentParser()
parser.add_argument('--directory',default='/config/sgcc')
args=parser.parse_args()
if not re.fullmatch(r'/[a-zA-Z0-9_/-]+',args.directory):parser.error('Use an absolute config path without shell syntax or spaces')
fields=[('status','Status',None,None),('fetched_at','Updated',None,'timestamp'),('source_date','Date',None,'date'),
 ('daily_usage','Daily','kWh','energy'),('valley_usage','Valley','kWh','energy'),('flat_usage','Flat','kWh','energy'),
 ('balance','Balance','CNY','monetary'),('amount_due','Due','CNY','monetary'),('bill_month','Bill Month',None,None),
 ('month_usage','Month Usage','kWh','energy'),('month_charge','Month Charge','CNY','monetary'),
 ('year_usage','Year Usage','kWh','energy'),('year_charge','Year Charge','CNY','monetary')]
sensors=[]
for key,name,unit,device_class in fields:
    sensor=dict(name='SGCC '+name,unique_id='sgcc_local_kit_'+key,
      command=f'python3 {args.directory}/snapshot.py {args.directory}/snapshot.json',scan_interval=300,
      value_template="{{ value_json.get('"+key+"') if value_json.get('"+key+"') is not none else 'unknown' }}",
      json_attributes=['source_date','bill_month','year','fetched_at','status'])
    if key=='status':sensor['json_attributes']+=['daily','months','daily_count','message','attempted_at']
    if unit:sensor['unit_of_measurement']=unit
    if device_class:sensor['device_class']=device_class
    sensors.append(dict(sensor=sensor))
print(json.dumps(sensors,ensure_ascii=False,indent=2))
