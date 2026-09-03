import json,sys,collections
S=sys.argv[1]
d=json.load(open(S+"/human_persuasion.json",encoding='utf-8'))
def mean(v): return sum(v)/len(v) if v else float('nan')
qmiss=qpres=0; roles=collections.Counter()
cells=collections.defaultdict(lambda: dict(g=0,rounds=0,buys=0,hi=0,lo=0,qmiss=0,pay=[],pos=0))
for g in d.values():
    c=g.get('config') or {}; me=g.get('your_player')
    st=g.get('state') or {}
    r1=st.get('player_1_role'); roles[(me,r1)]+=1
    role='seller' if (me=='player_1')==(r1=='seller') else 'buyer'
    if role!='buyer': continue
    m=c.get('v'); p=c.get('p'); price=c.get('product_price')
    k=(float(m),round(float(p),3))
    e=cells[k]; e['g']+=1
    res=g.get('result') or {}
    pay=res.get('player_2_payoff' if me=='player_2' else 'player_1_payoff')
    if pay is not None:
        e['pay'].append(pay/(price or 1))
        if pay>0: e['pos']+=1
    for h in st.get('history') or []:
        e['rounds']+=1
        if h.get('bought'):
            e['buys']+=1
            q=h.get('quality')
            if q=='high': e['hi']+=1
            elif q=='low': e['lo']+=1
            else: e['qmiss']+=1
print("your_player x player_1_role:",roles)
print("\n%-5s %-6s %5s %7s %7s %6s %6s %7s %9s %8s" % ("m","p","games","rounds","buy%","high","low","q?","pay/price","pos%"))
for k in sorted(cells):
    e=cells[k]
    if e['g']<10: continue
    b=e['buys'] or 1
    print("%-5s %-6.3f %5d %7d %6.1f%% %6d %6d %7d %9.2f %7.1f%%"
          % (k[0],k[1],e['g'],e['rounds'],100*e['buys']/max(1,e['rounds']),e['hi'],e['lo'],e['qmiss'],
             mean(e['pay']),100*e['pos']/e['g']))
tot=collections.Counter()
for e in cells.values():
    tot['g']+=e['g']; tot['buys']+=e['buys']; tot['hi']+=e['hi']; tot['lo']+=e['lo']; tot['qmiss']+=e['qmiss']; tot['pos']+=e['pos']
print("\nTOTAL buyer games %d  buys %d  high %d  low %d  quality-missing %d  positive-payoff games %d (%.1f%%)"
      % (tot['g'],tot['buys'],tot['hi'],tot['lo'],tot['qmiss'],tot['pos'],100*tot['pos']/tot['g']))
if tot['hi']+tot['lo']:
    print("human buyer hit rate on purchases: %.4f" % (tot['hi']/(tot['hi']+tot['lo'])))
