import json,sys,collections,math
S=sys.argv[1]; J=sys.argv[2]
def mean(v): return sum(v)/len(v) if v else float('nan')
reps={}
for f in ("human_replays.json","human_replays_rand.json","human_barg_recent.json"):
    reps.update(json.load(open(S+"/"+f,encoding='utf-8')))
H=collections.defaultdict(list)
for g in reps.values():
    if g.get('game_family')!='bargaining': continue
    c=g.get('config') or {}; pot=c.get('money_to_divide'); me=g.get('your_player')
    if not pot or not me: continue
    d1,d2=c.get('delta_1'),c.get('delta_2')
    du,dt=(d1,d2) if me=='player_1' else (d2,d1)
    hor='known' if c.get('max_rounds') else 'open'
    pay=(g.get('result') or {}).get('player_1_payoff' if me=='player_1' else 'player_2_payoff')
    if pay is None: continue
    H[(hor,me,du,dt)].append(pay/pot)
A=collections.defaultdict(list)
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']!='bargaining' or r.get('my_share') is None: continue
    A[('known' if r.get('hk') else 'open',r['slot'],r.get('d_us'),r.get('d_them'))].append(float(r['my_share']))
agg=collections.defaultdict(lambda:[[],[],0])
for k in sorted(set(H)&set(A)):
    if len(H[k])<25 or len(A[k])<100: continue
    e=agg[(k[0],k[1])]; e[0].append(mean(H[k])); e[1].append(mean(A[k])); e[2]+=len(H[k])
print("%-6s %-9s %6s %8s %8s %8s %8s" % ("hor","seat","cells","hu games","human","agent","diff"))
for k in sorted(agg):
    h,a,n=agg[k]
    print("%-6s %-9s %6d %8d %8.3f %8.3f %+8.3f" % (k[0],k[1],len(h),n,mean(h),mean(a),mean(h)-mean(a)))
