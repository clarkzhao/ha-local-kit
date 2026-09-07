"""Narwal identity preparation and read-only, allowlisted diagnostic reports.

Requires the separately installed sjmotew client; never imports HA config entries.
The report explains observations, not Home Assistant's live permission decisions.
"""
import argparse
import asyncio
import importlib
import json
import logging
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
FLAGS = (
    'is_docked', 'is_station_active', 'blocks_robot_start_for_dock_task',
    'has_recent_dock_drying_status', 'has_dock_drying_timer_snapshot',
    'has_unmapped_active_dock_task', 'has_error',
)
STATUSES = {
    'UNKNOWN', 'STANDBY', 'DOCKED', 'DOCKED_V2', 'CHARGED', 'CLEANING',
    'CLEANING_V2', 'CLEANING_ALT', 'CUSTOM_CLEANING', 'REMAPPING',
    'TASK_COMPLETED', 'ERROR',
}
MESSAGES = {
    'query_not_accepted': '设备未接受本次状态查询；不能据此判断功能是否受支持。',
    'error_reported': '状态报告故障；请先在官方 App 查看具体故障。',
    'dock_blocks_start': '当前快照的基站任务状态可能限制清洁设置或启动。',
    'drying_timer_missing': '检测到烘干状态但缺少计时快照；可能影响任务判断，也可能是新连接尚未取得完整信息。',
    'unmapped_dock_task': '上游模型无法识别当前基站任务；需要型号和固件适配证据。',
    'unknown_working_status': '工作状态缺失或未知；不能把未知状态当作待机或正常。',
    'polling_only': '按不广播型号读取；本次基础查询不能证明实时轨迹或清洁进度可用。',
    'insufficient_evidence': '没有足够证据解释不可用；未发现阻塞标志不代表所有控制已获许可。',
}


class ToolError(Exception):
    """Only fixed, non-sensitive error codes cross the CLI boundary."""


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        raise ToolError('invalid_input_file') from None


def validate_identity(value, *, require_key=True):
    if not isinstance(value, dict):
        raise ToolError('invalid_identity')
    device_id = value.get('device_id', '')
    key = value.get('product_key', '')
    host, port = value.get('host'), value.get('port', 9002)
    if not isinstance(device_id, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', device_id):
        raise ToolError('full_device_id_required')
    if (not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,253}', host)
            or type(port) is not int or not 1 <= port <= 65535):
        raise ToolError('invalid_endpoint')
    if not isinstance(key, str) or (key and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key)):
        raise ToolError('invalid_product_key')
    if require_key and not key:
        raise ToolError('product_key_required')
    broadcasts = value.get('supports_broadcasts', False)
    if type(broadcasts) is not bool:
        raise ToolError('invalid_broadcast_setting')
    return dict(device_id=device_id.lower(), product_key=key, host=host, port=port,
                supports_broadcasts=broadcasts)


def select_account(value, index, host, port=9002, broadcasts=False):
    rows = value.get('devices') if isinstance(value, dict) else None
    if not isinstance(rows, list) or not 1 <= index <= len(rows):
        raise ToolError('select_valid_device_index')
    row = rows[index - 1]
    if not isinstance(row, dict):
        raise ToolError('invalid_device_row')
    fields = {str(k).lower().replace('_', ''): v for k, v in row.items()}
    # productId, SN, iotId and a hostname suffix are deliberately NOT substitutes.
    return validate_identity(dict(device_id=fields.get('deviceid', ''),
        product_key=fields.get('productkey') or '', host=host, port=port,
        supports_broadcasts=broadcasts), require_key=False)


def private_output(path):
    path = Path(path).expanduser().absolute()
    resolved = path.resolve()
    if resolved == ROOT or ROOT in resolved.parents or path.is_symlink():
        raise ToolError('output_must_be_outside_public_checkout')
    if path.exists():
        raise ToolError('output_already_exists')
    return path


def write_private(path, identity):
    path = private_output(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Create exclusively: an existing identity is never silently overwritten.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(identity, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def explain(snapshot):
    """Only constrained scalars survive; arbitrary source strings never leak."""
    if not isinstance(snapshot, dict):
        raise ToolError('invalid_snapshot')
    observed = {key: snapshot.get(key) if type(snapshot.get(key)) is bool else None
                for key in FLAGS + ('query_accepted', 'supports_broadcasts')}
    status = snapshot.get('working_status')
    observed['working_status'] = status if isinstance(status, str) and status in STATUSES else 'UNKNOWN'
    code = snapshot.get('query_result_code')
    observed['query_result_code'] = code if type(code) is int and -1000 <= code <= 1000 else None
    reasons = []
    if observed['query_accepted'] is False:
        reasons.append('query_not_accepted')
    if observed['has_error'] is True:
        reasons.append('error_reported')
    if observed['blocks_robot_start_for_dock_task'] is True:
        reasons.append('dock_blocks_start')
    if (observed['has_recent_dock_drying_status'] is True
            and observed['has_dock_drying_timer_snapshot'] is not True):
        reasons.append('drying_timer_missing')
    if observed['has_unmapped_active_dock_task'] is True:
        reasons.append('unmapped_dock_task')
    if observed['working_status'] == 'UNKNOWN':
        reasons.append('unknown_working_status')
    if observed['supports_broadcasts'] is False:
        reasons.append('polling_only')
    if not reasons or reasons == ['polling_only']:
        reasons.append('insufficient_evidence')
    return dict(schema_version=1, source='provided_snapshot', observed=observed,
        findings=[dict(code=reason, message=MESSAGES[reason]) for reason in reasons],
        ha_permissions_evaluated=False,
        limitations=['新连接的基础快照不包含 HA 长期连接的全部任务历史。',
                     '缺失字段不证明硬件不支持；本报告不修改任何控制项的可用性。'])


def client_factory(component):
    component = Path(component).resolve()
    if not (component / 'narwal_client' / '__init__.py').is_file():
        raise ToolError('component_must_contain_narwal_client')
    sys.path.insert(0, str(component))
    try:
        return importlib.import_module('narwal_client').NarwalClient
    except (ImportError, AttributeError):
        raise ToolError('upstream_client_or_dependencies_missing') from None


async def query(identity, factory, *, discover=False, timeout=75):
    """Use only identity/base-status methods; disconnect on success or failure."""
    client = factory(host=identity['host'], port=identity['port'],
        device_id=identity['device_id'],
        topic_prefix='/' + identity['product_key'] if identity['product_key'] else None,
        supports_broadcasts=identity['supports_broadcasts'])
    try:
        async with asyncio.timeout(timeout):
            await client.connect()
            if discover and not identity['product_key']:
                await client.discover_device_id(timeout=max(1, timeout - 10))
                await client.drain_ws_buffer()
            info = await client.get_device_info()
            if str(info.device_id).lower() != identity['device_id']:
                raise ToolError('device_identity_mismatch')
            verified = validate_identity({**identity, 'product_key': info.product_key})
            if identity['product_key'] and verified['product_key'] != identity['product_key']:
                raise ToolError('product_key_mismatch')
            response = await client.get_status(full_update=True)
            snapshot = {key: getattr(client.state, key, None) for key in FLAGS}
            snapshot.update(working_status=getattr(getattr(client.state, 'working_status', None), 'name', None),
                query_result_code=int(response.result_code), query_accepted=bool(response.accepted),
                supports_broadcasts=identity['supports_broadcasts'])
            report = explain(snapshot)
            report['source'] = 'fresh_local_base_status'
            report['query_completed'] = True
            report['physical_actions_sent'] = False
            return verified, report
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=5)
        except (Exception, asyncio.CancelledError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    identity = sub.add_parser('identity', help='Confirm identity locally and save outside the public checkout')
    identity.add_argument('--account-file', required=True, type=Path)
    identity.add_argument('--device-index', required=True, type=int, help='1-based row in devices[]')
    identity.add_argument('--host', required=True)
    identity.add_argument('--port', type=int, default=9002)
    identity.add_argument('--broadcasts', action='store_true', help='Only when confirmed for this model')
    identity.add_argument('--output', required=True, type=Path)
    diagnose = sub.add_parser('diagnose', help='Query base state using a private identity file')
    diagnose.add_argument('--identity-file', required=True, type=Path)
    for command in (identity, diagnose):
        command.add_argument('--component', required=True, type=Path)
        command.add_argument('--timeout', type=float, default=75)
    offline = sub.add_parser('explain', help='Explain an allowlisted snapshot without contacting a device')
    offline.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    # Suppress dependency logging: connection URLs and protocol identities are private.
    logging.disable(sys.maxsize)
    try:
        if args.command == 'explain':
            report = explain(read_json(args.snapshot))
        else:
            if not 1 <= args.timeout <= 120:
                raise ToolError('timeout_must_be_1_to_120_seconds')
            if args.command == 'identity':
                private_output(args.output)
                identity = select_account(read_json(args.account_file), args.device_index,
                    args.host, args.port, args.broadcasts)
            else:
                identity = validate_identity(read_json(args.identity_file))
            verified, report = asyncio.run(query(identity, client_factory(args.component),
                discover=args.command == 'identity', timeout=args.timeout))
            if args.command == 'identity':
                write_private(args.output, verified)
                report['identity_saved'] = True
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except ToolError as error:
        code = str(error)
    except TimeoutError:
        code = 'query_timeout'
    except Exception:
        code = 'local_query_failed'
    print(json.dumps({'ok': False, 'error': code,
        'message': '检查输入格式、独立客户端依赖和局域网可达性；未输出原始异常或身份。'}, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main())
