"""Read-only projections of the formal plan; no new weights or task states."""
from datetime import datetime

from .core import snapshots


def recent_deliveries(data: dict, limit: int = 6) -> list[dict]:
    """Show commit-bound PR evidence, without inferring review or production approval.

    Evidence must be cited by a current snapshot. Historical snapshots/evidence stay
    in the audit ledger but do not silently reappear as a current delivery claim.
    """
    cited = {ref for event in snapshots(data).values() for ref in event['basis']}
    entries = [(i, e) for i, e in enumerate(data['evidence'])
               if e['id'] in cited and e['kind'] == 'pr' and e['source_commit']]
    ordered = sorted(entries, key=lambda item: (datetime.fromisoformat(
        item[1]['recorded_at'].replace('Z', '+00:00')), item[0]), reverse=True)
    return [e for _, e in ordered[:limit]]


def task_rows(data: dict, result: dict) -> list[dict]:
    """Keep implementation, test, review, merge and admission columns separate."""
    current = snapshots(data)
    rows = []
    for task in data['tasks']:
        event = current[task['id']]
        row = {'TASK': task['id'], '名称': task['title'], '阶段': task['stage'],
               '优先级': task['priority'], '状态': event['state'], '来源': task['origin'],
               '验收率 %': result['task_percent'][task['id']],
               '独立审查': event['review']['status'],
               'PR': ', '.join(f"#{p['number']} {p['state']}" for p in event['prs']) or '未创建',
               '生产准入': event['production']['status']}
        for kind, label in [('code', '代码'), ('offline', '离线'), ('live', '真实源'), ('ui', 'UI')]:
            statuses = [event['results'][a['id']]['status'] for a in task['acceptance']
                        if kind in a['evidence_kinds']]
            row[label] = ('未单列' if not statuses else 'FAIL' if 'FAIL' in statuses else
                          'PASS' if all(s == 'PASS' for s in statuses) else
                          'PARTIAL' if 'PASS' in statuses else 'UNVERIFIED')
        rows.append(row)
    return rows
