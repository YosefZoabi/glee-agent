"""Raw-history outcome counts and recorded deltas, including unfinished-game outcomes.

Uses the explicit platform outcome labels. Does not label every error or
cancellation a participant-caused abandonment, nor price a causal penalty.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from common import history_rows, mean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('history', nargs='+', type=Path)
    args = parser.parse_args()
    groups = defaultdict(list)
    try:
        rows = history_rows(args.history)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    for row in rows:
        if row.get('rating_delta') is not None:
            key = ((row.get('your_player_type') or 'agent'),
                   (row.get('result') or {}).get('outcome') or row.get('status') or 'unknown')
            groups[key].append(row['rating_delta'])
    print(json.dumps({'deduplicated_records': len(rows), 'outcomes': [
        dict(track=key[0], outcome=key[1], n=len(v), mean_recorded_delta=mean(v), sum_recorded_deltas=sum(v))
        for key, v in sorted(groups.items())], 'interpretation': 'Observed deltas, not causal costs.'}, indent=2))


if __name__ == '__main__':
    main()
