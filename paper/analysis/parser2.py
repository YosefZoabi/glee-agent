import json,sys,collections
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from glee_agent.strategies.persuasion import _NEGATIVE_HINTS as FINAL
EXPLICIT = FINAL[:FINAL.index("do not buy")+1]          # original block only
HEDGED   = FINAL[:FINAL.index("not the one")+1]         # + hedged refusals
ADDED    = FINAL                                        # + final-night block
def pos(msg,h):
    if msg is None: return False
    s=str(msg).strip().lower()
    return bool(s) and not any(x in s for x in h)
rows=[json.loads(l) for l in open(sys.argv[1],encoding='utf-8')]
print("games %d" % len(rows))
def run(base,new,tag):
    fl=b=hi=lo=0
    for g in rows:
        for h in g.get('history') or []:
            m=h.get('seller_message')
            if m is None: continue
            if pos(m,base) and not pos(m,new):
                fl+=1
                if h.get('bought'):
                    b+=1
                    if h.get('quality')=='high': hi+=1
                    elif h.get('quality')=='low': lo+=1
    print("%-34s reclassified %5d  bought %4d  low %4d  high %3d  dud %.3f"
          % (tag,fl,b,lo,hi,lo/max(1,lo+hi)))
run(EXPLICIT,HEDGED,"hedged block (earlier commit)")
run(HEDGED,ADDED,"final-night block")
run(EXPLICIT,ADDED,"both blocks vs explicit-only")
# how many messages contain 'not this one'
c=sum(1 for g in rows for h in (g.get('history') or [])
      if h.get('seller_message') and "not this one" in str(h['seller_message']).lower())
print("messages containing 'not this one': %d" % c)
tot=sum(1 for g in rows for h in (g.get('history') or []) if h.get('seller_message'))
print("total buyer rounds with a message: %d" % tot)
