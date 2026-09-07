"""Read only billing fields from the already authenticated Shanghai website.

The website's private Vue data format can change. This focused adapter excludes
account objects, addresses and access tokens; it never submits login forms.
Field discovery informed by ARC-MX/sgcc_electricity_new; implementation is local.
"""
from datetime import datetime
import math


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(str(value).replace(',', '').strip())
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def read_components(page):
    # Project only fields needed by our snapshot, instead of serializing Vue state.
    return page.evaluate('''() => {
      const result = [], seen = new Set();
      const pick = (obj, keys) => Object.fromEntries(keys.map(k => [k, obj?.[k]]));
      for (const el of document.querySelectorAll('*')) {
        const vm = el.__vue__;
        if (!vm || seen.has(vm)) continue;
        seen.add(vm);
        const data = {};
        for (const key of ['powerData', 'tableData_t']) {
          const value = vm[key];
          if (!value || !Array.isArray(value.mothEleList)) continue;
          data[key] = {
            dataInfo: pick(value.dataInfo, ['year','totalEleNum','totalEleCost']),
            mothEleList: value.mothEleList.map(r => pick(r, ['month','monthEleNum','monthEleCost','begDate','endDate','mrDate','max']))
          };
        }
        for (const key of ['tableData','new_sevenEleList','sevenEleList']) {
          if (!Array.isArray(vm[key])) continue;
          data[key] = vm[key].filter(r => r && r.day).map(r =>
            pick(r, ['day','dayElePq','thisVPq','thisNPq','thisPPq','thisTPq']));
        }
        if (Object.keys(data).length) result.push({data});
      }
      return result;
    }''')


def daily_rows(components):
    for key in ('tableData', 'new_sevenEleList', 'sevenEleList'):
        for component in components:
            rows = component.get('data', {}).get(key)
            if not isinstance(rows, list):
                continue
            output = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                day = str(row.get('day', ''))
                total = number(row.get('dayElePq'))
                try:
                    if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
                        continue
                except ValueError:
                    continue
                if total is None or total < 0:
                    continue
                output[day] = dict(date=day, total_usage=total,
                    **{name: number(row.get(field)) for name, field in (
                        ('valley_usage','thisVPq'), ('flat_usage','thisNPq'),
                        ('peak_usage','thisPPq'), ('tip_usage','thisTPq'))})
            if output:
                return [output[day] for day in sorted(output)]
    return []


def monthly_summary(components):
    for component in components:
        for key in ('powerData', 'tableData_t'):
            power = component.get('data', {}).get(key)
            if not isinstance(power, dict):
                continue
            months = {}
            for row in power.get('mothEleList') or []:
                ym = str(row.get('month', '')).replace('-', '')
                try:
                    period = datetime.strptime(ym, '%Y%m').strftime('%Y-%m')
                    if len(ym) != 6:
                        continue
                except ValueError:
                    continue
                usage, charge = number(row.get('monthEleNum')), number(row.get('monthEleCost'))
                if usage is None or usage < 0 or charge is None:
                    continue
                months[period] = dict(month=period, total_usage=usage, total_charge=charge,
                    begin_date=row.get('begDate'), end_date=row.get('endDate'),
                    meter_read_time=row.get('mrDate'), is_max=bool(row.get('max')))
            if months:
                info = power.get('dataInfo') or {}
                year = str(info.get('year', ''))
                if len(year) != 4 or not year.isdigit():
                    raise RuntimeError('data_incomplete')
                return dict(months=[months[k] for k in sorted(months)], year=year,
                    yearly_usage=number(info.get('totalEleNum')),
                    yearly_charge=number(info.get('totalEleCost')))
    raise RuntimeError('data_incomplete')
