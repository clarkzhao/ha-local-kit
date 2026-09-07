"""Read a manually authenticated SGCC session. Never submit login/captcha/payment.

Browser state stays private on the Mac. HA receives numeric/date data only.
"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo

from .page_data import number, daily_rows, read_components, monthly_summary

DATA = None
HA = None
ZONE = ZoneInfo('Asia/Shanghai')
ORIGIN = 'https://www.95598.cn'
CDP_URL = 'http://127.0.0.1:9227'


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)


def account(text):
    found = re.search(r'用电户号\s*[:：]\s*(\d{8,})', text)
    if not found:
        raise RuntimeError('account_unconfirmed')
    return hashlib.sha256(found.group(1).encode()).hexdigest()[:16]


def check_page(page):
    if '/login' in page.url:
        raise RuntimeError('login_required')
    if '退出' not in page.locator('body').inner_text():
        raise RuntimeError('login_required')


def visit(page, route):
    if page.url.split('?')[0] != ORIGIN + route:
        page.goto(ORIGIN + route, wait_until='domcontentloaded', timeout=40000)
    # Account data is asynchronous; a fixed short sleep mislabels slow loading.
    try:
        page.wait_for_function(r"/用电户号\s*[:：]\s*\d{8,}/.test(document.body.innerText)", timeout=35000)
    except Exception:
        check_page(page)
        raise RuntimeError('account_unconfirmed')
    check_page(page)


def fetch(headless=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        owned = headless
        if owned:
            if not (DATA / 'session.private.json').is_file():
                raise RuntimeError('login_required')
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(storage_state=str(DATA / 'session.private.json'), locale='zh-CN', timezone_id='Asia/Shanghai')
            session = json.loads((DATA / 'session-storage.private.json').read_text()) if (DATA / 'session-storage.private.json').exists() else {}
            context.add_init_script('if(location.origin === "https://www.95598.cn") { const data = ' + json.dumps(session) + '; for(const [k,v] of Object.entries(data)) sessionStorage.setItem(k,v); }')
            page = context.new_page()
        else:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            page = next(pg for ctx in browser.contexts for pg in ctx.pages if pg.url.startswith(ORIGIN + '/'))
            context = page.context
        try:
            visit(page, '/osgweb/my95598')
            home = page.locator('body').inner_text()
            identity = account(home)
            pin = DATA / 'account-pin.json'
            if pin.exists() and json.loads(pin.read_text())['id'] != identity:
                raise RuntimeError('account_changed')
            def amount(label):
                match = re.search(label + r'\s*[:：]\s*(-?[\d,.]+)\s*元', home)
                return number(match.group(1)) if match else None
            balance, due = amount('账户余额'), amount('应交金额')
            visit(page, '/osgweb/electricityCharge')
            if account(page.locator('body').inner_text()) != identity:
                raise RuntimeError('account_changed')
            deadline = time.monotonic() + 30
            while True:
                try:
                    monthly = monthly_summary(read_components(page))
                    break
                except RuntimeError:
                    if time.monotonic() >= deadline:
                        raise
                    page.wait_for_timeout(500)
            page.get_by_text('日用电量', exact=True).click(timeout=10000)
            page.wait_for_timeout(5000)
            if page.get_by_text('近30天', exact=True).is_visible():
                page.get_by_text('近30天', exact=True).click()
                page.wait_for_timeout(5000)
            components = read_components(page)
            check_page(page)
            if account(page.locator('body').inner_text()) != identity:
                raise RuntimeError('account_changed')
            daily = daily_rows(components)
            months = sorted([m for m in monthly.get('months', [])
                if re.fullmatch(r'\d{4}-\d{2}', m.get('month', '')) and number(m.get('total_usage')) is not None], key=lambda m: m['month'])
            if not daily or not months:
                raise RuntimeError('data_incomplete')
            now = datetime.now(ZONE).isoformat(timespec='seconds')
            # Store only this dedicated SGCC session; files never enter HA/www.
            state = context.storage_state(indexed_db=True)
            state['cookies'] = [c for c in state['cookies'] if c['domain'].lstrip('.') in ('95598.cn', 'www.95598.cn')]
            state['origins'] = [o for o in state['origins'] if o['origin'] == ORIGIN]
            atomic(DATA / 'session.private.json', state)
            atomic(DATA / 'session-storage.private.json', page.evaluate('Object.fromEntries(Object.entries(sessionStorage))'))
            atomic(pin, {'id': identity})
            with sqlite3.connect(DATA / 'history.sqlite3') as db:
                db.execute('CREATE TABLE IF NOT EXISTS daily (account TEXT, day TEXT, payload TEXT, PRIMARY KEY(account,day))')
                db.execute('CREATE TABLE IF NOT EXISTS monthly (account TEXT, month TEXT, payload TEXT, PRIMARY KEY(account,month))')
                db.executemany('INSERT OR REPLACE INTO daily VALUES(?,?,?)', [(identity, r['date'], json.dumps(r)) for r in daily])
                db.executemany('INSERT OR REPLACE INTO monthly VALUES(?,?,?)', [(identity, r['month'], json.dumps(r)) for r in months])
            latest, bill = daily[-1], months[-1]
            snapshot = dict(status='ok', fetched_at=now, attempted_at=now, source_date=latest['date'],
                daily_usage=latest['total_usage'], valley_usage=latest['valley_usage'], flat_usage=latest['flat_usage'],
                balance=balance, amount_due=due, bill_month=bill['month'], month_usage=bill['total_usage'], month_charge=bill['total_charge'],
                year=monthly.get('year'), year_usage=monthly.get('yearly_usage'), year_charge=monthly.get('yearly_charge'),
                daily=daily, months=months, daily_count=len(daily), message='最近一次采集成功；账单与日用电按各自日期展示')
            atomic(DATA / 'snapshot.json', snapshot)
            atomic(HA / 'snapshot.json', snapshot)
            print(json.dumps({k: snapshot[k] for k in ('status','source_date','daily_usage','bill_month','month_usage','month_charge','daily_count')}, ensure_ascii=False))
        finally:
            if owned:
                browser.close()


def main():
    import fcntl
    global DATA, HA, CDP_URL
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--ha-dir', type=Path, required=True)
    parser.add_argument('--cdp-url', default=CDP_URL)
    args = parser.parse_args()
    CDP_URL = args.cdp_url
    DATA, HA = args.state_dir.resolve(), args.ha_dir.resolve()
    os.umask(0o077)
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / 'collect.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            def deadline(_signum, _frame):
                raise RuntimeError('collection_timeout')
            signal.signal(signal.SIGALRM, deadline)
            signal.alarm(240)
            fetch(args.headless)
        except Exception as exc:
            reason = str(exc) if str(exc) in ('login_required','account_changed','account_unconfirmed','data_incomplete') else 'collection_failed'
            snapshot = json.loads((DATA / 'snapshot.json').read_text()) if (DATA / 'snapshot.json').exists() else {}
            snapshot.update(status=reason, attempted_at=datetime.now(ZONE).isoformat(timespec='seconds'),
                            message='需要重新人工登录' if reason == 'login_required' else '采集未成功，保留旧值；请检查会话或页面')
            atomic(DATA / 'snapshot.json', snapshot)
            atomic(HA / 'snapshot.json', snapshot)
            print(json.dumps({'status': reason}, ensure_ascii=False))
            sys.exit(1)
        finally:
            signal.alarm(0)


if __name__ == '__main__':
    main()
