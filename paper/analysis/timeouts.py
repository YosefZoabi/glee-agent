"""Joined-log outcome diagnostic; this input can omit abandoned games.

Use timeouts2.py or timeouts3.py with finalized raw history for timeout counts.
This command explicitly describes only the records present in the joined log.
"""
import json
from collections import defaultdict
from common import inputs, jsonl, mean

args = inputs(__doc__, 'joined')
groups = defaultdict(list)
for row in jsonl(args.joined):
    if row.get('rd') is not None:
        groups[(row.get('fam'), row.get('outcome') or 'unknown')].append(row['rd'])
print(json.dumps({'warning': 'Joined logs may omit the abandoned games being studied.',
                  'rows': [dict(family=k[0], outcome=k[1], n=len(v), mean_delta=mean(v))
                           for k,v in groups.items()], 'causal_cost_estimate': None}, indent=2))
