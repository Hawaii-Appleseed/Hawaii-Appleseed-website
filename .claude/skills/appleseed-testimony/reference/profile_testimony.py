import re, glob, statistics as st, collections, os

FILES = sorted(f for f in glob.glob(os.path.expanduser(
    '~/HawaiiAppleseed/writing-bot/testimony/*/*.txt'))
    if not os.path.basename(f).startswith('sample_'))

GREET  = re.compile(r'^(dear|aloha|to the honorable|good (morning|afternoon))', re.I)
CLOSE  = re.compile(r'^(mahalo|thank you for the opportunity|sincerely|respectfully submitted)', re.I)
ORGSIG = re.compile(r'^Hawai.i Appleseed( Center)?[,\s]*$', re.I)
BOILER = 'advocates for economic justice for and with'

def parse(raw):
    raw = raw.replace('﻿','')
    raw = re.split(r'_{6,}\s*$', raw, flags=re.M)[0] if re.search(r'_{6,}\s*\n\s*\[1\]', raw) else raw
    raw = re.split(r'\n_{6,}\n(?=\s*\[1\])', raw)[0]
    lines=[l.strip() for l in raw.split('\n')]
    lines=[l for l in lines if l and l!='.' and not re.match(r'^_{3,}$',l)
           and 'LEJ-SERVER' not in l and not l.startswith('\\\\')
           and not re.match(r'^\[\d+\]',l) and not l.startswith('http')
           and BOILER not in l]
    gi = next((i for i,l in enumerate(lines) if GREET.match(l)), None)
    header = lines[:gi] if gi is not None else []
    rest   = lines[gi+1:] if gi is not None else lines
    tailstart = max(0, len(rest)-3)
    ci = next((i for i,l in enumerate(rest) if i>=tailstart and CLOSE.match(l)), len(rest))
    body   = rest[:ci]; closing = rest[ci:]
    greet  = lines[gi] if gi is not None else None
    return header, greet, body, closing

def sentences(p):
    p = re.sub(r'\b(Mr|Mrs|Ms|Dr|St|No|Rep|Sen|vs|etc)\.', r'\1', p)
    p = p.replace('U.S.','US')
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+', p) if len(x.strip().split())>1]

docs=[]
for f in FILES:
    h,g,b,c = parse(open(f,encoding='utf-8',errors='replace').read())
    heads=[l for l in b if len(l.split())<=9 and not re.search(r'[.!?;,]$',l)
           and '\t' not in l and not re.match(r'^[\d$(]',l)]
    paras=[l for l in b if l not in heads and '\t' not in l and len(l.split())>=8]
    docs.append(dict(f=os.path.basename(f), hdr=h, greet=g, heads=heads, paras=paras,
                     close=c, text=' '.join(paras)))
docs=[d for d in docs if len(d['text'].split())>=50]

ALL=' '.join(d['text'] for d in docs)
W=len(ALL.split())
sents=[s for d in docs for p in d['paras'] for s in sentences(p)]
SL=[len(s.split()) for s in sents]
N=len(docs)
def pct(n,d=N): return f'{100*n/d:.0f}%'
def dist(xs):
    xs=sorted(xs); q=lambda p: xs[min(int(p*len(xs)),len(xs)-1)]
    return f'median {st.median(xs):>4.0f}   p10 {q(.10):>3.0f}  p25 {q(.25):>3.0f}  p75 {q(.75):>3.0f}  p90 {q(.90):>3.0f}   range {xs[0]}–{xs[-1]}'

print('='*72)
print(f'TESTIMONY STYLE PROFILE — {N} documents, {W:,} body words, {len(sents)} sentences')
print('='*72)

print('\n## SHAPE')
print(f'  Body words / testimony : {dist([len(d["text"].split()) for d in docs])}')
print(f'  Paragraphs / testimony : {dist([len(d["paras"]) for d in docs])}')
print(f'  Sentences / paragraph  : {dist([len(sentences(p)) for d in docs for p in d["paras"]])}')
print(f'  Words / sentence       : {dist(SL)}   mean {st.mean(SL):.1f}  stdev {st.stdev(SL):.1f}')
print(f'    under 12 words: {pct(sum(1 for x in SL if x<12),len(SL))}    over 35 words: {pct(sum(1 for x in SL if x>35),len(SL))}')
print(f'  Subheads / testimony   : {dist([len(d["heads"]) for d in docs])}   ({pct(sum(1 for d in docs if d["heads"]))} of docs use any)')

print('\n## THE FIXED SCAFFOLD  (header block, before the greeting)')
pats=[(r'^Testimony of the','"Testimony of the Hawaiʻi Appleseed Center..."'),
      (r'^(Support|Opposition|Comments) for','"Support for HB #### – Relating to X"'),
      (r'Committee on','committee name line'),
      (r'^(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day','hearing date + time line')]
for p,l in pats:
    print(f'  {pct(sum(1 for d in docs if any(re.search(p,x,re.I) for x in d["hdr"]))):>5} of docs  {l}')
print('\n  Position is declared in the HEADER TITLE, not a prose sentence:')
t=collections.Counter()
for d in docs:
    for x in d['hdr']:
        m=re.match(r'^(Support|Strong support|Opposition|Comments|In support)\s+(for|of)\s', x, re.I)
        if m: t[m.group(0).strip()]+=1
for k,v in t.most_common(): print(f'      {v:>3}  "{k} ..."')

print('\n## GREETING')
g=collections.Counter()
for d in docs:
    if not d['greet']: g['(none)']+=1; continue
    named = 'named chair' if re.match(r'Dear Chair \w', d['greet']) else 'generic'
    end = d['greet'][-1]
    g[f'Dear Chair …, Vice Chair …, and members of the Committee{end}  [{named}]']+=1
for k,v in g.most_common(6): print(f'  {v:>3}  {k}')
print(f'  ends with colon: {pct(sum(1 for d in docs if d["greet"] and d["greet"].endswith(":")))}   '
      f'comma: {pct(sum(1 for d in docs if d["greet"] and d["greet"].endswith(",")))}')

print('\n## FIRST BODY SENTENCE')
o=collections.Counter()
for d in docs:
    s=sentences(d['paras'][0]) if d['paras'] else []
    if s: o[' '.join(s[0].split()[:6])]+=1
for k,v in o.most_common(7): print(f'  {v:>3}  {k}…')
print(f'\n  opens "Thank you for the opportunity": {pct(sum(1 for d in docs if d["paras"] and d["paras"][0].lower().startswith("thank you")))}')

print('\n## CLOSING')
c=collections.Counter()
for d in docs:
    c[re.sub(r'\s+',' ',d['close'][0])[:58]+'…' if d['close'] else '(no closing line)']+=1
for k,v in c.most_common(7): print(f'  {v:>3}  {k}')

print('\n## THE ASK')
for p,l in [(r'\burge\b','urge'),(r'respectfully urge','"respectfully urge"'),
            (r'\bwe (ask|request)\b','"we ask/request"'),(r'\bplease\b','"please"'),
            (r'\bsupport (this|the) (bill|measure)\b','"support this bill/measure"'),
            (r'\bpass (this|HB|SB)\b','"pass this/HB/SB"')]:
    print(f'  {pct(sum(1 for d in docs if re.search(p,d["text"],re.I))):>5} of docs  {l}')

print('\n## PERSON  (per 1,000 words)')
for p,l in [(r'\bwe\b','we'),(r'\bour\b','our'),(r'\bus\b','us'),(r'\bI\b','I'),(r'\bmy\b','my'),
            (r'Hawai.i Appleseed','"Hawaiʻi Appleseed" (3rd person self-reference)')]:
    n=len(re.findall(p,ALL))
    print(f'  {1000*n/W:>5.1f}   ({n:>3})  {l:<45} in {pct(sum(1 for d in docs if re.search(p,d["text"])))} of docs')

print('\n## MECHANICS')
def c_(p,f=0): return len(re.findall(p,ALL,f))
rows=[('exclamation points',c_(r'!')),('rhetorical questions',c_(r'\?')),
      ('semicolons',c_(r';')),('colons mid-prose',c_(r'\w: ')),
      ('em dash — UNSPACED',c_(r'\w—\w')),('em dash — spaced',c_(r'\w — \w')),
      ('en dash – as a DASH (word–word, non-numeric)',len([m for m in re.findall(r'\w+–\w+',ALL) if not re.match(r'^\d',m)])),
      ('en dash – in numeric ranges',len([m for m in re.findall(r'\d+–\d+',ALL)])),
      ('"percent" spelled out',c_(r'\bpercent\b')),('% sign',c_(r'%')),
      ('parentheticals',c_(r'\(')),('bulleted/numbered list lines',sum(1 for d in docs for p in d['paras'] if re.match(r'^[•\-\d]\.?\s',p))),
      ('direct quotations',c_(r'“'))]
for l,n in rows: print(f'  {n:>4}  {l}')
ct=len(re.findall(r"\b\w+[’']\w+\b",ALL))
print(f'  {ct:>4}  contractions  ({1000*ct/W:.1f} per 1,000 words)')
print(f'\n  ʻokina: Hawaiʻi correct {c_("Hawai"+chr(0x02BB)+"i")} | bare "Hawaii" {c_(r"Hawaii\b")} | curly-quote {c_("Hawai"+chr(0x2018)+"i")}')
haw=[(w,c_(w,re.I)) for w in ['keiki','kūpuna','ʻohana','mahalo','ʻāina','aloha','kauhale']]
print('  Hawaiian words: ' + ', '.join(f'{w} {n}' for w,n in haw if n) + f'  — {sum(n for _,n in haw)} total in {W:,} words')

print('\n## EVIDENCE')
print(f'  {c_(r"\$[\d,]+"):>4}  dollar figures        ({c_(r"[$][\d,]+")/N:.1f} / testimony)')
print(f'  {c_(r"\b\d[\d,.]*\b"):>4}  numerals              ({1000*c_(r"\b\d[\d,.]*\b")/W:.0f} per 1,000 words)')
print(f'  {c_(r"\b(HB|SB|HR|HCR|SCR|SR)\s?\d+"):>4}  bill references       ({pct(sum(1 for d in docs if re.search(r"(HB|SB)\s?\d+",d["text"])))} of docs)')
print(f'  {c_(r"\bAct \d+"):>4}  Act citations')
print(f'  {c_(r"\bSection \d|\bHawai.i Revised Statutes|\bHRS\b"):>4}  statute citations')

print('\n## MODALS — prescription vs hedge')
for p in ['would','will','must','should','can','could','may','might']:
    print(f'  {1000*c_(r"\b"+p+r"\b",re.I)/W:>5.1f} /1k  {p}')

print('\n## ANTI-PATTERNS')
z=[(r'\bsome (argue|say|claim|believe)\b','some argue/say/claim'),(r'\bopponents\b','opponents'),
   (r'\bcritics\b','critics'),(r'\bit is (important|worth) (to note|noting)\b','it is important to note'),
   (r'\bin conclusion\b','in conclusion'),(r'\bfirst and foremost\b','first and foremost'),
   (r'\bat the end of the day\b','at the end of the day'),(r'\bdelve\b','delve'),
   (r'\btapestry\b','tapestry'),(r'\bnavigat\w+\b','navigate/navigating'),
   (r'\bmoreover\b','moreover'),(r'\bfurthermore\b','furthermore'),(r'\badditionally\b','additionally'),
   (r'\bhowever\b','however'),(r'\bcrucial\b','crucial'),(r'\bvital\b','vital'),
   (r'\brobust\b','robust'),(r'\bleverage\b','leverage'),(r'\bstakeholder\b','stakeholder'),
   (r'\bimpactful\b','impactful'),(r'\bunderscore\b','underscore')]
for p,l in z:
    n=c_(p,re.I); mark='  ← ZERO' if n==0 else ''
    print(f'  {n:>4}  {l}{mark}')

print('\n## SUBHEADS (body only)')
hs=[h for d in docs for h in d['heads']]
for h in hs[:18]: print(f'      {h}')
if hs:
    cap=sum(1 for h in hs if sum(1 for w in h.split() if len(w)>3 and w[0].isupper())>=max(1,sum(1 for w in h.split() if len(w)>3)))
    verb=sum(1 for h in hs if re.search(r'\b(is|are|will|must|should|would|can|helps?|makes?|works?)\b',h,re.I))
    print(f'\n  {len(hs)} total | median {st.median([len(h.split()) for h in hs]):.0f} words | '
          f'Title Case {pct(cap,len(hs))} | contains a finite verb {pct(verb,len(hs))}')
