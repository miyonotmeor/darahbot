"""Every one of the quiz questions (English AND Bahasa Melayu) must be answered correctly by the chatbot."""
import re
import bot_engine as bot, quiz
data=bot.load_data(); Q=quiz.build_questions(data)
def norm(x): return x.lower().replace(',','')
bad=[]
for q in Q:
  for lang,key in (('en','en'),('bm','ms')):
    r=bot.answer(q[key],data,None,lang); txt=norm(r.get('text',''))
    show=str(q['show']).split(' (')[0]
    if q['kind']=='num':
        v=q['answer']; cands={f"{v:,.0f}".replace(',',''), f"{v:.1f}", f"{v:g}", str(int(round(v)))}
        hit=any(c in txt for c in cands)
    elif q['kind']=='bool':
        yes=bool(q['answer']); w=set(re.findall(r"[a-z]+",txt))
        hit=(yes and bool(w&{'yes','ya','rose','up','naik','increase','increased','more','higher','lebih','meningkat','tinggi'})) or ((not yes) and bool(w&{'no','tidak','fell','down','turun','decrease','dropped','fewer','lower','kurang','menurun','bukan'}))
    elif q['kind'] in ('month','day'):
        names=(quiz.MONTHS,quiz.MONTHS_MS) if q['kind']=='month' else (quiz.DAYS,quiz.DAYS_MS)
        hit=names[0][q['answer']].lower() in txt or names[1][q['answer']].lower() in txt
    else:
        hit=norm(show)[:6] in txt or any(norm(a)[:6] in txt for a in q.get('accept',[]) if len(a)>3)
    if r['kind']!='ok' or not hit: bad.append((q['id'],lang,r['kind'],q[key][:60],show[:25],r['text'][:70].replace('\n',' ')))
for b in bad: print(b)
print(f"\nRESULT: {len(Q)*2-len(bad)} passed, {len(bad)} failed")
