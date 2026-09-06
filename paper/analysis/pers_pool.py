"""Observational persuasion comparison, pooled by blind-buy expected-value regime.

Two positional inputs produce Table 1 diagnostics. Optional --buyer-replays adds
purchase-conditioned quality rates. Missing outcomes are excluded, never zero
imputed. Welch-form t values are descriptive and have no dependence adjustment.
"""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from common import buyer_seat, jsonl, mean


def band(m, p):
    product = m*p
    return 'mp<1' if product < .995 else ('mp=1' if product < 1.005 else 'mp>1')


def welch_t(human, agent):
    if len(human) < 2 or len(agent) < 2:
        return None
    variance = statistics.variance(human)/len(human) + statistics.variance(agent)/len(agent)
    return (mean(human)-mean(agent))/math.sqrt(variance) if variance > 0 else None


def compare(human_games, agent_games):
    human, agent = defaultdict(list), defaultdict(list)
    omitted = {'human_unknown_role': 0, 'human_missing_payoff': 0, 'agent_missing_payoff': 0,
               'human_invalid_price': 0, 'agent_invalid_price': 0}
    for game in human_games:
        state = game.get('state') or {}
        if state.get('player_1_role') not in ('buyer', 'seller') or game.get('your_player') not in ('player_1','player_2'):
            omitted['human_unknown_role'] += 1
            continue
        if not buyer_seat(game):
            continue
        config = game.get('config') or {}; me = game['your_player']
        payoff = (game.get('result') or {}).get(me+'_payoff')
        if payoff is None:
            omitted['human_missing_payoff'] += 1
            continue
        price = config.get('product_price')
        if price is None or price <= 0:
            omitted['human_invalid_price'] += 1
            continue
        human[band(float(config['v']), float(config['p']))].append(payoff/price)
    for row in agent_games:
        if row.get('fam') != 'persuasion' or row.get('role') != 'buyer':
            continue
        if row.get('my_pay') is None:
            omitted['agent_missing_payoff'] += 1
            continue
        price = row.get('price')
        if price is None or price <= 0:
            omitted['agent_invalid_price'] += 1
            continue
        agent[band(float(row['m']), float(row['p']))].append(row['my_pay']/price)
    rows = []
    for key in sorted(set(human) | set(agent)):
        h, a = human[key], agent[key]
        rows.append(dict(regime=key, human_n=len(h), agent_n=len(a),
                         human_mean=mean(h) if h else None, agent_mean=mean(a) if a else None,
                         t_human_minus_agent=welch_t(h, a)))
    return {'rows': rows, 'omitted': omitted,
            'limitations': 'Pooled regimes, not exact configuration matching; no dependence adjustment or causal identification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('human_dir', type=Path)
    parser.add_argument('joined', type=Path)
    parser.add_argument('--buyer-replays', type=Path)
    args = parser.parse_args()
    data = json.loads((args.human_dir/'human_persuasion.json').read_text(encoding='utf-8'))
    result = compare(data.values() if isinstance(data, dict) else data, jsonl(args.joined))
    if args.buyer_replays:
        counts = dict(high=0, low=0, unknown=0)
        for game in jsonl(args.buyer_replays):
            for row in game.get('history') or []:
                if row.get('bought'):
                    quality = row.get('quality')
                    counts[quality if quality in ('high','low') else 'unknown'] += 1
        known = counts['high']+counts['low']
        result['agent_purchase_quality'] = dict(**counts, known_quality_n=known,
                                               high_rate=counts['high']/known if known else None)
    else:
        result['agent_purchase_quality'] = 'Not computed; supply --buyer-replays for this separate cohort.'
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
