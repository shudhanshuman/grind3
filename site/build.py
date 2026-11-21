#!/usr/bin/env python3
"""Build grind3/site/index.html from the theory.md files. Re-run after editing any .md."""
import html, re
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "index.html"

# slug, folder, short name, theory h, build h (low, high), tier, language
PROJECTS = [
    ("order-book", "order_book", "Order book", 7, (30, 40), "core", "C++"),
    ("itch-fpga", "itch_fpga", "ITCH on FPGA", 11, (40, 50), "core", "SystemVerilog"),
    ("chess-engine", "chess_engine", "Chess engine", 9, (40, 60), "core", "C++ + PyGame"),
    ("codeforces-dsa", "codeforces_dsa", "Codeforces / DSA", 0, (45, 55), "core", "C++"),
    ("vector-db", "vector_db", "Vector database", 7, (30, 40), "stretch", "C++ / Rust"),
    ("neural-accelerator", "neural_accelerator", "Neural accelerator", 9, (40, 50), "stretch", "SystemVerilog + Python"),
    ("compiler", "compiler", "Compiler", 9, (40, 60), "stretch", "C / C++ / Python"),
]


BLURBS = {
    "order-book": "Price-time matching engine plus a NASDAQ book rebuilt from real ITCH data, benchmarked to the nanosecond.",
    "itch-fpga": "SystemVerilog decoder for ITCH 5.0 and MoldUDP64 on a 64-bit stream, checked against the C++ parser.",
    "chess-engine": "From zero: bitboards, perft-verified move generation, alpha-beta search, then NNUE and AlphaZero ideas.",
    "codeforces-dsa": "Daily routine and topic ladder from 1330 to 1600+, plus the interview patterns contests skip.",
    "vector-db": "HNSW, IVF-PQ, SIMD distances, WAL persistence and filtering, benchmarked on SIFT1M against hnswlib.",
    "neural-accelerator": "Seven options for one NPU block. The pick: an int8 systolic array, bit-exact against PyTorch.",
    "compiler": "Four flavours, from bytecode VM to C-to-ARM64 to an ML compiler that could target your accelerator.",
}


def fix_md(text: str) -> str:
    """Make GitHub-style markdown palatable to python-markdown."""
    out, prev = [], ""
    for line in text.splitlines():
        # 2-space nested list indent -> 4 spaces
        m = re.match(r"^( +)([-*]|\d+\.) ", line)
        if m and len(m.group(1)) % 2 == 0 and len(m.group(1)) % 4 != 0:
            line = " " * (len(m.group(1)) * 2) + line.lstrip()
        starts_block = bool(re.match(r"^(\s*[-*] |\s*\d+\. |\|)", line))
        prev_is_block = bool(re.match(r"^(\s*[-*] |\s*\d+\. |\||\s{4,})", prev))
        if starts_block and prev.strip() and not prev_is_block:
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def render(md_text: str):
    md_text = fix_md(md_text)
    title_m = re.search(r"^# (.+)$", md_text, re.M)
    title = title_m.group(1).strip() if title_m else ""
    title = re.sub(r"\s+[—-]\s+Theory.*$", "", title)
    md_text = re.sub(r"^# .+\n", "", md_text, count=1, flags=re.M)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    body = re.sub(r"<table>", '<div class="tw"><table class="stack">', body)
    body = body.replace("</table>", "</table></div>")
    body = re.sub(r"<pre><code([^>]*)>", r'<div class="code"><button class="cp" type="button">Copy</button><pre><code\1>', body)
    body = body.replace("</code></pre>", "</code></pre></div>")
    body = body.replace("<hr />", "")
    # split into lead (before first h2) + collapsible h2 sections
    parts = re.split(r"<h2>(.*?)</h2>", body)
    lead, secs = parts[0], []
    for i in range(1, len(parts), 2):
        secs.append((parts[i], parts[i + 1]))
    return title, lead, secs


def sections_html(slug, secs, open_first=False):
    out = []
    for i, (h, content) in enumerate(secs):
        h = re.sub(r"^\d+\.\s*", "", h)
        sid = f"{slug}-s{i}"
        out.append(
            f'<details class="sec" id="{sid}"{" open" if open_first and i == 0 else ""}>'
            f'<summary><span class="n">{i+1}</span><span class="h">{h}</span></summary>'
            f'<div class="sb">{content}</div></details>'
        )
    return "\n".join(out)


def chart_rows():
    mx = 70
    rows = []
    for slug, _, name, th, (lo, hi), tier, _ in PROJECTS:
        mid = (lo + hi) / 2
        rows.append(
            f'<a class="row" href="#{slug}"><span class="rn">{name}</span>'
            f'<span class="track"><span class="bt" style="width:{th/mx*100:.1f}%"></span>'
            f'<span class="bb {tier}" style="width:{mid/mx*100:.1f}%"></span>'
            f'</span>'
            f'<span class="rv">{th + lo}–{th + hi} h</span></a>'
        )
    return "\n".join(rows)


def main():
    readme_title, readme_lead, readme_secs = render((ROOT / "README.md").read_text())
    views, cards, nav = [], [], []
    for slug, folder, name, th, (lo, hi), tier, lang in PROJECTS:
        title, lead, secs = render((ROOT / folder / "theory.md").read_text())
        nav.append(f'<a href="#{slug}">{name}</a>')
        lead_txt = re.sub(r"<[^>]+>", "", lead).strip()
        first = html.escape(BLURBS[slug])
        cards.append(
            f'<a class="card {tier}" href="#{slug}"><span class="tier">{"Core" if tier=="core" else "Stretch"}</span>'
            f'<strong>{name}</strong><span class="cd">{first}</span>'
            f'<span class="meta">{lang} · {th+lo}–{th+hi} h · {len(secs)} sections</span></a>'
        )
        views.append(
            f'<section class="view" id="v-{slug}" hidden><div class="band phead">'
            f'<a class="back" href="#home">← All tracks</a><h2 class="pt">{title}</h2>'
            f'<div class="lead">{lead}</div>'
            f'<div class="tools"><input type="search" class="q" placeholder="Search this track" aria-label="Search {name}">'
            f'<button type="button" class="ex">Expand all</button></div></div>'
            f'<div class="band secs">{sections_html(slug, secs)}</div></section>'
        )
    page = TEMPLATE
    for k, v in {
        "nav": "\n".join(nav),
        "chart": chart_rows(),
        "cards": "\n".join(cards),
        "readme_lead": readme_lead,
        "readme_secs": sections_html("home", readme_secs),
        "views": "\n".join(views),
    }.items():
        page = page.replace("{" + k + "}", v)
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(page)//1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>grind3 winter manual</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
/* VOICE: a calm, dense engineering field manual read at night on a phone.
   IDEA: a lab notebook's index page plus a time-budget plate.
   PICTURE: the hours plate, theory vs build per track, against the month you have.
   COLOUR and TYPE: near-black sea ground in both themes, sky ink, pink as the warning accent. Hanken Grotesk, JetBrains Mono for code.
   LAYOUT: index view (plate, cards, overview), one view per track with collapsible numbered sections. */
:root{color-scheme:dark;--bg:#05080d;--bg2:#0b1119;--bg3:#111a26;--line:#1d2a3a;--ink:#e3eaf2;--mute:#8a9bb0;--sky:#8fd3ff;--pink:#ff5c8a;--mint:#7fe0b8}
:root[data-theme=light],:root[data-theme=dark]{color-scheme:dark}
*{box-sizing:border-box;min-width:0}
html{scroll-padding-top:72px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "Hanken Grotesk",system-ui,sans-serif;overflow-x:clip}
a{color:var(--sky)}
.band{padding:clamp(20px,4vw,48px) max(5vw,16px);max-width:1240px;margin:0 auto}
header.top{border-bottom:1px solid var(--line);background:rgba(5,8,13,.92);backdrop-filter:blur(8px)}
@media(min-width:900px){header.top{position:sticky;top:0;z-index:5}}
.topin{max-width:1240px;margin:0 auto;padding:10px max(5vw,16px);display:flex;gap:14px;align-items:center}
.brand{font-weight:700;color:var(--ink);text-decoration:none;flex:none;font-size:18px}
.scroll{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none}.scroll::-webkit-scrollbar{display:none}
.scroll a{flex:none;color:var(--mute);text-decoration:none;padding:10px 12px;border-radius:8px;font-size:15px;min-height:44px;display:flex;align-items:center}
.scroll a:hover,.scroll a.on{color:var(--ink);background:var(--bg3)}
h1,.pt{font-weight:300;font-size:clamp(34px,6vw,52px);line-height:1.05;margin:0 0 12px;text-wrap:balance;letter-spacing:-.01em}
.sub{color:var(--mute);font-size:17px;max-width:68ch;margin:0}
.plate{background:var(--bg2);border:1px solid var(--line);border-radius:16px;padding:clamp(16px,3vw,28px);margin-top:24px}
.kpis{display:flex;flex-wrap:wrap;gap:12px 36px;margin-bottom:20px}
.kpi b{display:block;font-weight:300;font-size:clamp(32px,6vw,48px);line-height:1;white-space:nowrap}
.kpi span{color:var(--mute);font-size:14px}
.kpi.warn b{color:var(--pink)}
.row{display:grid;grid-template-columns:minmax(0,150px) minmax(0,1fr) 84px;gap:12px;align-items:center;padding:9px 0;text-decoration:none;color:var(--ink);border-top:1px solid var(--line)}
.row:hover .rn{color:var(--sky)}
.rn{font-size:15px}.rv{text-align:right;font-variant-numeric:tabular-nums;color:var(--mute);font-size:14px;white-space:nowrap}
.track{position:relative;height:18px;display:flex;background:var(--bg);border-radius:4px}
.bt{background:#2f4a66;border-radius:4px 0 0 4px}.bb{background:var(--sky);border-radius:0 4px 4px 0}.bb.stretch{background:#4f7fa3}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin-top:14px;color:var(--mute);font-size:13px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,280px),1fr));gap:14px}
.card{display:flex;flex-direction:column;gap:8px;padding:18px;background:var(--bg2);border:1px solid var(--line);border-radius:14px;text-decoration:none;color:var(--ink);transition:border-color .2s,transform .2s}
.card:hover{border-color:var(--sky);transform:translateY(-2px)}
.card strong{font-size:21px;font-weight:600}.cd{color:var(--mute);font-size:15px;flex:1}
.meta{font-size:13px;color:var(--mute)}
.tier{align-self:flex-start;font-size:13px;padding:2px 10px;border-radius:99px;background:rgba(143,211,255,.12);color:var(--sky)}
.stretch .tier{background:rgba(255,92,138,.12);color:var(--pink)}
h3.sh{font-size:22px;font-weight:600;margin:8px 0 14px}
.back{display:inline-flex;min-height:44px;align-items:center;text-decoration:none;color:var(--mute);font-size:15px}
.lead{color:#c3cfdc;max-width:75ch}
.lead blockquote,.sb blockquote{margin:14px 0;padding:12px 16px;border-left:3px solid var(--sky);background:var(--bg2);border-radius:0 10px 10px 0}
.lead blockquote p,.sb blockquote p{margin:6px 0}
.tools{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}
.q{flex:1 1 220px;font:inherit;font-size:16px;color:var(--ink);background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-height:44px}
button{font:inherit;font-size:15px;color:var(--ink);background:var(--bg3);border:1px solid var(--line);border-radius:10px;padding:8px 14px;min-height:44px;cursor:pointer}
button:hover{border-color:var(--sky)}
:focus-visible{outline:2px solid var(--sky);outline-offset:2px}
.secs{padding-top:0}
details.sec{border:1px solid var(--line);border-radius:14px;background:var(--bg2);margin-bottom:10px;overflow:hidden}
details.sec>summary{list-style:none;cursor:pointer;display:flex;gap:14px;align-items:center;padding:14px 18px;min-height:56px}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary::after{content:"+";margin-left:auto;color:var(--mute);font-size:22px;flex:none}
details.sec[open]>summary::after{content:"–"}
details.sec[open]>summary{border-bottom:1px solid var(--line);background:var(--bg3)}
.n{flex:none;width:30px;height:30px;border-radius:8px;display:grid;place-items:center;background:var(--bg);color:var(--sky);font-size:14px;font-weight:600}
.h{font-size:18px;font-weight:600;line-height:1.3}
.sb{padding:4px 18px 18px;max-width:100%}
.sb p,.sb li{max-width:75ch}
.sb h3{font-size:17px;color:var(--sky);margin:24px 0 8px}
.sb li{margin:4px 0}.sb li::marker{color:var(--mute)}
strong{color:#fff;font-weight:600}
code{font:14px/1.5 "JetBrains Mono",ui-monospace,monospace;background:var(--bg);border:1px solid var(--line);padding:1px 5px;border-radius:5px;overflow-wrap:anywhere}
.code{position:relative;margin:14px 0}
pre{overflow-x:auto;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:16px;margin:0}
pre code{border:0;padding:0;background:none;overflow-wrap:normal;font-size:13px}
.cp{position:absolute;top:6px;right:6px;min-height:32px;padding:4px 10px;font-size:13px}
.tw{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:15px}
th{text-align:left;color:var(--mute);font-weight:600;border-bottom:1px solid var(--line);padding:8px 10px;white-space:nowrap}
td{border-bottom:1px solid var(--line);padding:8px 10px;vertical-align:top}
tr:hover td{background:rgba(143,211,255,.03)}
mark{background:rgba(255,92,138,.3);color:#fff;border-radius:3px}
.none{color:var(--mute);padding:12px 0}
footer{color:var(--mute);font-size:13px;text-align:center;padding:32px 16px}
@media(max-width:600px){
 .row{grid-template-columns:minmax(0,1fr) 72px;gap:4px 10px}.track{grid-column:1/-1;order:3}
 table{font-size:14px}.stack thead{display:none}.stack tr{display:grid;padding-block:10px;border-bottom:1px solid var(--line)}
 .stack td{display:flow-root;border:0;padding:3px 0;padding-inline-start:7.5em;text-align:start}
 .stack td::before{content:attr(data-l);float:inline-start;width:7em;margin-inline-start:-7.5em;white-space:normal;color:var(--mute);font-size:13px}
 .stack td:empty{display:none}.sb{padding:4px 14px 14px}details.sec>summary{padding:12px 14px}
}
@media(prefers-reduced-motion:reduce){.card{transition:none}.card:hover{transform:none}}
</style></head><body>
<header class="top"><div class="topin"><a class="brand" href="#home">grind3</a><nav class="scroll">{nav}</nav></div></header>
<main>
<section class="view" id="v-home">
 <div class="band">
  <h1>Winter break 2026: the theory manual</h1>
  <p class="sub">Seven tracks, about 30 days. Everything to know before writing code: concepts, design trade-offs, interview questions and exact resources.</p>
  <div class="plate">
   <div class="kpis">
    <div class="kpi warn"><b>330–420 h</b><span>to finish all seven well</span></div>
    <div class="kpi"><b>250–300 h</b><span>a focused month gives you</span></div>
    <div class="kpi"><b>4 core + 1</b><span>recommended scope</span></div>
   </div>
   {chart}
   <div class="legend"><span><i style="background:#2f4a66"></i>Theory</span><span><i style="background:var(--sky)"></i>Build (core)</span><span><i style="background:#4f7fa3"></i>Build (stretch)</span></div>
  </div>
 </div>
 <div class="band" style="padding-top:0"><h3 class="sh">Tracks</h3><div class="cards">{cards}</div></div>
 <div class="band" style="padding-top:0"><h3 class="sh">Plan, C++ ramp-up and how interviews have changed</h3><div class="lead">{readme_lead}</div><div style="margin-top:14px">{readme_secs}</div></div>
</section>
{views}
</main>
<footer>grind3 · built from the theory.md files in ~/grind3</footer>
<script>
{
 const views=[...document.querySelectorAll('.view')], links=[...document.querySelectorAll('.scroll a')];
 const show=()=>{
  const h=location.hash.slice(1); let id='v-home', sec=null;
  if(h && document.getElementById('v-'+h)) id='v-'+h;
  else if(h && document.getElementById(h)?.classList.contains('sec')){sec=document.getElementById(h);id=sec.closest('.view').id;}
  views.forEach(v=>v.hidden=v.id!==id);
  links.forEach(a=>a.classList.toggle('on','v-'+a.hash.slice(1)===id));
  const t=document.querySelector('.scroll a.on'); if(t) t.scrollIntoView({block:'nearest',inline:'center'});
  if(sec){sec.open=true;sec.scrollIntoView();} else window.scrollTo(0,0);
  try{localStorage.setItem('g3-last',location.hash)}catch(e){}
 };
 window.addEventListener('hashchange',show);
 if(!location.hash){try{const l=localStorage.getItem('g3-last');if(l)history.replaceState(null,'',l)}catch(e){}}
 show();
 for(const t of document.querySelectorAll('table.stack')){const hd=[...t.rows[0].cells].map(c=>c.textContent);for(const r of [...t.rows].slice(1))[...r.cells].forEach((c,i)=>c.dataset.l=hd[i]||'');}
 document.addEventListener('click',e=>{
  const b=e.target.closest('.cp'); if(b){const txt=b.nextElementSibling.textContent;navigator.clipboard.writeText(txt).then(()=>{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1200)}).catch(()=>{b.textContent='Select text to copy'});return;}
  const x=e.target.closest('.ex'); if(x){const v=x.closest('.view');const ds=[...v.querySelectorAll('details.sec')];const open=!ds.every(d=>d.open);ds.forEach(d=>d.open=open);x.textContent=open?'Collapse all':'Expand all';}
 });
 for(const q of document.querySelectorAll('.q')){
  const v=q.closest('.view'), ds=[...v.querySelectorAll('details.sec')];
  const none=document.createElement('p');none.className='none';none.textContent='No section mentions that.';none.hidden=true;v.querySelector('.secs').append(none);
  q.addEventListener('input',()=>{const s=q.value.trim().toLowerCase();let n=0;
   ds.forEach(d=>{const hit=!s||d.textContent.toLowerCase().includes(s);d.hidden=!hit;if(hit)n++;d.open=!!s&&hit;});none.hidden=n>0;});
 }
}
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
