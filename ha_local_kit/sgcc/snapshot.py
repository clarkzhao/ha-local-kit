"""HA command_line: local file only, no cloud or browser launch."""
from datetime import datetime, timezone
import json
from pathlib import Path

def read(path):
    try:
        data = json.loads(path.read_text())
        if data.get('status') == 'ok':
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(data['fetched_at'])).total_seconds()
            if age > 36 * 3600:
                data['status'] = 'stale'
                data['message'] = '超过36小时未成功采集，显示保留数据'
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'no_data', 'message': '尚无可读取的数据'}

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('snapshot',type=Path)
    print(json.dumps(read(parser.parse_args().snapshot), ensure_ascii=False))
