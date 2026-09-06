"""Describe timeout counts and timing; do not infer a persistent rating cost.

The old fixed-target calculation mixed rating scales. A finite cluster and a
stationary stream of timeouts are different estimands. This script retains only
observed deltas. Even their sum is not a final-standing effect or causal cost.
"""
import argparse
import collections
from pathlib import Path
from common import history_rows, mean


def summarize(rows):
    results = []
    for track in ('agent', 'human'):
        selected = [r for r in rows if (r.get('your_player_type') or 'agent') == track
                    and r.get('rating_delta') is not None
                    and (r.get('result') or {}).get('outcome') is not None]
        timed_out = [r for r in selected if (r.get('result') or {}).get('outcome') == 'timeout']
        if not timed_out:
            continue
        hours = collections.Counter((r.get('completed_at') or '')[:13] for r in timed_out)
        clustered = [n for hour, n in hours.items() if hour and n >= 3]
        deltas = [r['rating_delta'] for r in timed_out]
        results.append(dict(track=track, timeout_games=len(timed_out), rated_games=len(selected),
                            mean_recorded_delta=mean(deltas), sum_recorded_deltas=sum(deltas),
                            hours_with_at_least_3_timeouts=len(clustered), timeouts_in_those_hours=sum(clustered),
                            timeouts_without_timestamp=sum(not r.get('completed_at') for r in timed_out)))
    return results


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('history', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({'outcome_definition': 'timeout only; not every adverse outcome',
                          'rows': summarize(history_rows(args.history)),
                          'persistent_cost_estimate': None}, indent=2))
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
