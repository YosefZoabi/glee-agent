"""Human vs agent: the paired within-game counterfactual, plus nego + persuasion."""
import json, sys, collections, math
S=sys.argv[1]; J=sys.argv[2]
def mean(v): return sum(v)/len(v) if v else float('nan')
reps={}
for f in ("human_replays.json","human_replays_rand.json","human_barg_recent.json","human_persuasion.json"):
    reps.update(json.load(open(S+"/"+f,encoding='utf-8')))
hist={h['game_id']:h for h in json.load(open(S+"/human_hist_full.json",encoding='utf-8'))}

print("=== 1. BARGAINING: was refusing right? (paired, within game) ===")
def score(rows):
    """rows: (best_refused_share, round_refused, banked_share, delta)"""
    gain=[]
    for br,rr,bk,d in rows:
        if br is None: continue
        gain.append(bk-br*(d**(rr-1)))     # banked minus 'sign it now' at that round
    return gain
hrows=[]
for g in reps.values():
    if g.get('game_family')!='bargaining': continue
    c=g.get('config') or {}; pot=c.get('money_to_divide'); me=g.get('your_player')
    if not pot or not me: continue
    d=c.get('delta_1') if me=='player_1' else c.get('delta_2')
    res=g.get('result') or {}; ar=res.get('agreed_round')
    pay=res.get('player_1_payoff' if me=='player_1' else 'player_2_payoff')
    if pay is None or d is None: continue
    mk='alice_gain' if me=='player_1' else 'bob_gain'
    best=None
    for m in g.get('moves') or []:
        if m.get('move_type')!='offer': continue
        dd=m.get('move_data') or {}
        if mk not in dd: continue
        rnd=m.get('round') or 0
        if (rnd%2==1)==(me=='player_1'): continue      # our own proposal
        if ar and rnd==ar: continue                    # this is the one we signed
        s=dd[mk]/pot
        if best is None or s>best[0]: best=(s,rnd)
    if best: hrows.append((best[0],best[1],pay/pot,d))
arows=[]
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']!='bargaining' or r.get('my_share') is None or r.get('d_us') is None: continue
    faced=r.get('faced') or []; ar=r.get('accept_round')
    best=None
    for e in faced:
        rnd,sh,act=e[0],e[1],e[2]
        if act=='accept': continue
        if sh is None: continue
        if best is None or sh>best[0]: best=(sh,rnd)
    if best: arows.append((best[0],best[1],float(r['my_share']),float(r['d_us'])))
for tag,rows in (("HUMAN",hrows),("AGENT",arows)):
    g=score(rows)
    pos=sum(1 for x in g if x>1e-9); neg=sum(1 for x in g if x<-1e-9)
    print("  %-6s n=%-6d best refused %.3f  banked %.3f  net value of refusing %+.4f of pot"
          % (tag,len(g),mean([r[0] for r in rows]),mean([r[2] for r in rows]),mean(g)))
    print("         refusing paid in %d games, cost in %d  (%.1f%% right)"
          % (pos,neg,100*pos/max(1,pos+neg)))

print("\n=== 2. NEGOTIATION: human outcomes ===")
nh=[h for h in hist.values() if h['game_family']=='negotiation']
oc=collections.Counter((h.get('result') or {}).get('outcome') for h in nh)
print("  n=%d  " % len(nh) + ", ".join("%s %.1f%%"%(k,100*v/len(nh)) for k,v in oc.most_common()))
sur=[]; rnds=[]
for g in reps.values():
    if g.get('game_family')!='negotiation': continue
    c=g.get('config') or {}; me=g.get('your_player'); res=g.get('result') or {}
    sv,bv=c.get('seller_value'),c.get('buyer_value')
    if sv is None or bv is None or bv<=sv: continue
    pay=res.get('player_1_payoff' if me=='player_1' else 'player_2_payoff')
    scale=c.get('product_price_order') or 1
    if pay is None: continue
    s=(bv-sv)*scale
    if s>0: sur.append(pay/s)
    if res.get('agreed_round'): rnds.append(res['agreed_round'])
print("  surplus captured (complete-info replays, n=%d): %.3f   median agreed round %.0f"
      % (len(sur),mean(sur),sorted(rnds)[len(rnds)//2] if rnds else -1))

print("\n=== 3. PERSUASION: human buyer vs agent buyer, by cell ===")
HB=collections.defaultdict(lambda: [0,0,0,0])   # rounds, buys, high_buys, games
HZ=collections.Counter(); HG=collections.Counter()
for g in reps.values():
    if g.get('game_family')!='persuasion': continue
    c=g.get('config') or {}
    if g.get('your_player')!='player_2': continue      # buyer seat
    m=c.get('v'); p=c.get('p')
    if m is None or p is None: continue
    k=(float(m),round(float(p),3))
    st=g.get('state') or {}
    h=st.get('history') or []
    res=g.get('result') or {}
    HG[k]+=1
    if (res.get('player_2_payoff') or 0)<=0: HZ[k]+=1
    for e in h:
        HB[k][0]+=1
        if e.get('bought'):
            HB[k][1]+=1
            if e.get('quality')=='high': HB[k][2]+=1
AB=collections.defaultdict(lambda:[0,0,0])
for ln in open(J,encoding='utf-8'):
    r=json.loads(ln)
    if r['fam']!='persuasion' or r.get('role')!='buyer': continue
    k=(float(r['m']),round(float(r['p']),3))
    AB[k][0]+=1
    if (r.get('my_pay') or 0)<=0: AB[k][1]+=1
    AB[k][2]+=r.get('buys') or 0
print("  %-5s %-6s | %6s %8s %8s %8s | %7s %8s" % ("m","p","hu n","hu buy%","hu dud%","hu zero%","ag n","ag zero%"))
for k in sorted(set(HG)&set(AB)):
    rr,bb,hh,_=HB[k]
    if HG[k]<12 or bb<10: continue
    print("  %-5s %-6.3f | %6d %8.1f%% %8.1f%% %8.1f%% | %7d %8.1f%%"
          % (k[0],k[1],HG[k],100*bb/rr,100*(1-hh/bb),100*HZ[k]/HG[k],AB[k][0],100*AB[k][1]/AB[k][0]))
tz=sum(HZ.values()); tg=sum(HG.values())
az=sum(v[1] for v in AB.values()); ag=sum(v[0] for v in AB.values())
print("  OVERALL  human banks zero in %.2f%% of buyer games (n=%d); agent %.2f%% (n=%d)"
      % (100*tz/tg,tg,100*az/ag,ag))
