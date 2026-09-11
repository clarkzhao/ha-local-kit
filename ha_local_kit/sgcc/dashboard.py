"""Generate a native HA sections view using pinned community cards.

Charts use source dates, never the sensor polling time. No template-generated
Markdown tables and no fabricated zero for a missing reading.
"""
import json

ENTITY = 'sensor.sgcc_status'


def chart(title, monthly=False, usage=False):
    fields = [('total_usage', '月度用电', '#159D91')] if usage else [('total_charge', '月度电费', '#326EDB')] if monthly else [
        ('total_usage', '总用电', '#326EDB'),
        ('valley_usage', '谷时', '#159D91'),
        ('flat_usage', '平时', '#93A4BD')]
    array, date = ('months', 'month') if monthly else ('daily', 'date')
    suffix = '-01T00:00:00+08:00' if monthly else 'T00:00:00+08:00'
    series = []
    for key, label, color in fields:
        generator = (
            f"return (entity.attributes.{array} || []).map(r => "
            f"[new Date(r.{date} + '{suffix}').getTime(), "
            f"r.{key} == null ? null : Number(r.{key})])"
            ".filter(p => Number.isFinite(p[0])).sort((a,b) => a[0]-b[0]);")
        series.append(dict(entity=ENTITY, name=label, color=color,
            unit='元' if monthly and not usage else '度', type='line', extend_to=False,
            data_generator=generator, float_precision=2,
            header_actions=dict(tap_action=dict(action='none'))))
    return dict(type='custom:apexcharts-card', section_mode=True,
        grid_options=dict(columns=12, rows=7), graph_span='365d' if monthly else '31d',
        span={'start':'year'} if monthly else {'end':'day','offset':'-1d'},
        header=dict(show=True, title=title, show_states=False,
                    title_actions=dict(tap_action=dict(action='none'))),
        series=series, yaxis=[dict(min=0, decimals=0)],
        apex_config=dict(chart=dict(height=260, toolbar=dict(show=False),
                                    zoom=dict(enabled=False), animations=dict(enabled=False)),
            stroke=dict(width=2.6, curve='straight'), markers=dict(size=2.5, strokeWidth=0),
            grid=dict(borderColor='#dce3ec', strokeDashArray=4),
            legend=dict(show=True, position='top', horizontalAlign='left', fontSize='12px'),
            xaxis=dict(labels=dict(datetimeUTC=False, format='MM月' if monthly else 'MM/dd'),
                       axisBorder=dict(show=False), axisTicks=dict(show=False)),
            tooltip=dict(shared=True, x=dict(format='yyyy年MM月' if monthly else 'yyyy-MM-dd'))))


def table(title, monthly=False):
    array, date = ('months', 'month') if monthly else ('daily', 'date')
    columns = [dict(name='月份' if monthly else '日期', id='period', data=array, modify='x.'+date)]
    fields = [('total_usage','用电 / 度'), ('total_charge','电费 / 元')] if monthly else [
        ('total_usage','总用电 / 度'), ('valley_usage','谷时'), ('flat_usage','平时')]
    for key, label in fields:
        columns.append(dict(name=label, data=array, align='right',
            modify=f"x.{key} == null ? '—' : Number(x.{key}).toFixed(2)"))
    return dict(type='custom:flex-table-card', title=title, entities=dict(include=ENTITY),
        columns=columns, sort_by='period-', strict=True,
        tap_action=dict(action='none'), hold_action=dict(action='none'),
        grid_options=dict(columns=12, rows='auto'), css={
            'ha-card': 'border-radius:18px;overflow:hidden;box-shadow:none;',
            'ha-card > div': 'max-height:408px;overflow:auto;padding:0 14px 14px;',
            'table': 'width:100%;border-collapse:collapse;padding:0;font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap;',
            'thead th': 'position:sticky;top:0;z-index:1;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--secondary-text-color);font-size:12px;font-weight:500;padding:13px 8px;border-bottom:1px solid var(--divider-color);',
            'tbody tr td': 'padding:12px 8px;height:20px;border-bottom:1px solid var(--divider-color);',
            'tbody tr:nth-child(even)': 'background:rgba(100,130,170,.045);',
            'tbody tr:hover': 'background:rgba(50,110,219,.08);'})


def metric_actions(key):
    detail = 'daily' if key in ('daily','valley','flat') else 'year' if key.startswith('year_') else 'monthly'
    action = dict(action='navigate', navigation_path='/home-rooms/electricity-'+detail)
    return dict(tap_action=action, icon_tap_action=action,
        hold_action=dict(action='none'), double_tap_action=dict(action='none'),
        icon_hold_action=dict(action='none'), icon_double_tap_action=dict(action='none'))


def tile(key, name, icon, color='blue'):
    return dict(type='tile',entity='sensor.sgcc_'+key,name=name,icon=icon,color=color,
        grid_options=dict(columns=6,rows=1), **metric_actions(key))


def build_view():
    return dict(title='电费', path='electricity', icon='mdi:transmission-tower',
        type='sections', max_columns=2, dense_section_placement=False, sections=[
        dict(type='grid',column_span=2,cards=[
            dict(type='heading',heading='用电与账单',heading_style='title',icon='mdi:transmission-tower'),
            dict(type='markdown',grid_options=dict(columns='full',rows='auto'),content=
                "{% set s = states('sensor.sgcc_status') %}\n"
                "**国家电网** &nbsp; {{ '● 数据正常' if s == 'ok' else '⚠ ' ~ {'stale':'数据已过期','login_required':'登录已失效，需要人工登录','collection_failed':'采集失败','account_changed':'户号变化','account_unconfirmed':'未能核验户号','data_incomplete':'数据不完整'}.get(s,s) }}\n\n"
                "{% if s != 'ok' %}**当前显示上次成功采集的保留数据。**{% if s == 'login_required' %} 请在国网专用浏览器中重新登录。{% endif %}\n\n{% endif %}"
                "日用电截至 **{{ states('sensor.sgcc_date') }}** · 最近账单 **{{ states('sensor.sgcc_bill_month') }}** · "
                "更新 {{ as_local(as_datetime(states('sensor.sgcc_updated'))).strftime('%m-%d %H:%M') if has_value('sensor.sgcc_updated') else '等待数据' }}"),
            tile('daily','最近日用电','mdi:lightning-bolt'),
            tile('month_charge','最近账单电费','mdi:receipt-text-outline'),
            tile('year_usage','本年累计用电','mdi:chart-line','teal'),
            tile('due','应交金额','mdi:wallet-outline','teal')]),
        dict(type='grid',cards=[chart('近 31 天 · 日用电'),table('每日明细')]),
        dict(type='grid',cards=[chart('本年 · 月度电费',True),table('月度账单',True)]),
        dict(type='grid',column_span=2,cards=[dict(type='markdown',
            grid_options=dict(columns='full',rows='auto'), content=
            "国网数据存在出账延迟，折线按**实际用电日 / 账单月**排列。平时、谷时沿用国网字段；缺失值显示 —。采集失败保留旧值，并在顶部提示。\n\n"
            "[返回房间总览](/home-rooms/overview)")])])


def build_detail_views():
    views=[]
    for path,title,graph,detail,description in [
        ('daily','每日用电',chart('最近 31 天 · 每天一个数据点'),table('每日明细'),
         "日用电截至 **{{ states('sensor.sgcc_date') }}**。按实际用电日展示，单位：度；没有小时级读数。"),
        ('monthly','月度电费',chart('本年 · 每月账单电费',True),table('月度账单',True),
         "最近账单 **{{ states('sensor.sgcc_bill_month') }}** · 电费 **{{ states('sensor.sgcc_month_charge') }} 元**。\n\n应交金额 **{{ states('sensor.sgcc_due') }} 元** · 余额 **{{ states('sensor.sgcc_balance') }} 元**（当前账户快照）。"),
        ('year','本年用电',chart('本年 · 每月用电量',True,True),table('月度用电与账单',True),
         "网站本年累计 **{{ states('sensor.sgcc_year_usage') }} 度**。下图按账单月展示每月电量，不把累计值的采集记录当作小时用电。")]:
        views.append(dict(title=title,path='electricity-'+path,subview=True,
            back_path='/home-rooms/electricity',type='sections',max_columns=1,sections=[
                dict(type='grid',cards=[dict(type='heading',heading=title,heading_style='title'),
                    dict(type='markdown',content=description+'\n\n采集状态：{{ states("sensor.sgcc_status") }} · 数据更新：{{ states("sensor.sgcc_updated") }}'),graph,detail])]))
    return views


def apply_dashboard(rooms):
    """Replace the SGCC views and route SGCC metric cards in other views too."""
    managed=[build_view(),*build_detail_views()]
    paths={v['path'] for v in managed}
    rooms['views']=[v for v in rooms['views'] if v.get('path') not in paths]+managed
    def walk(value):
        if isinstance(value,dict):
            entity=value.get('entity','')
            if value.get('type')=='tile' and entity.startswith('sensor.sgcc_'):
                value.update(metric_actions(entity.removeprefix('sensor.sgcc_')))
            for item in value.values(): walk(item)
        elif isinstance(value,list):
            for item in value: walk(item)
    walk(rooms)
    return rooms


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Generate an electricity dashboard; stdout is JSON (valid YAML).')
    parser.add_argument('--dashboard-path', default='home-rooms')
    parser.add_argument('--entity-prefix', default='sgcc')
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'[a-z][a-z0-9_-]*',args.dashboard_path) or not re.fullmatch(r'[a-z][a-z0-9_]*',args.entity_prefix):
        parser.error('invalid dashboard path or entity prefix')
    value=json.dumps({'title':'用电与账单','views':[build_view(),*build_detail_views()]},ensure_ascii=False,indent=2)
    print(value.replace('/home-rooms/','/'+args.dashboard_path+'/').replace('sensor.sgcc_','sensor.'+args.entity_prefix+'_'))

if __name__ == '__main__':
    main()
