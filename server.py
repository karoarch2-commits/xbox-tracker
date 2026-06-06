from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse, json, os

PORT  = int(os.environ.get("PORT", 8080))
IQD   = 1550

MARKETS = [
    {"market":"US","flag":"🇺🇸","label":"United States"},
    {"market":"TR","flag":"🇹🇷","label":"Turkey"},
    {"market":"AR","flag":"🇦🇷","label":"Argentina"},
    {"market":"NG","flag":"🇳🇬","label":"Nigeria"},
    {"market":"BR","flag":"🇧🇷","label":"Brazil"},
    {"market":"IN","flag":"🇮🇳","label":"India"},
    {"market":"RU","flag":"🇷🇺","label":"Russia"},
    {"market":"CO","flag":"🇨🇴","label":"Colombia"},
    {"market":"SA","flag":"🇸🇦","label":"Saudi Arabia"},
    {"market":"EG","flag":"🇪🇬","label":"Egypt"},
    {"market":"PL","flag":"🇵🇱","label":"Poland"},
    {"market":"MX","flag":"🇲🇽","label":"Mexico"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "MS-CV": "0",
}

def ms_fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())

def search(query):
    url = ("https://storeedgefd.dsx.mp.microsoft.com/v8.0/sdk/products"
           f"?market=US&locale=en-US&deviceFamily=Windows.Xbox"
           f"&query={urllib.parse.quote(query)}")
    data     = ms_fetch(url)
    products = data.get("Products", [])
    games = []
    for p in products[:12]:
        lp    = (p.get("LocalizedProperties") or [{}])[0]
        title = lp.get("ProductTitle","")
        pid   = p.get("ProductId","")
        imgs  = lp.get("Images",[])
        img   = ""
        for purpose in ["Tile","BoxArt","Logo"]:
            f = next((i for i in imgs if i.get("ImagePurpose")==purpose), None)
            if f:
                img = f.get("Uri","")
                if img and not img.startswith("http"): img = "https:"+img
                break
        if pid and title:
            games.append({"id":pid,"title":title,"img":img})
    return games

def prices(pid):
    result = []
    for reg in MARKETS:
        try:
            url = (f"https://displaycatalog.mp.microsoft.com/v7.0/products/{pid}"
                   f"?market={reg['market']}&languages=en-US,neutral&MS-CV=0")
            data  = ms_fetch(url)
            prod  = data.get("Product",{})
            skus  = prod.get("DisplaySkuAvailabilities",[])
            lp    = (prod.get("LocalizedProperties") or [{}])[0]
            title = lp.get("ProductTitle","")
            imgs  = lp.get("Images",[])
            img   = ""
            for purpose in ["Tile","BoxArt","Logo"]:
                f = next((i for i in imgs if i.get("ImagePurpose")==purpose), None)
                if f:
                    img = f.get("Uri","")
                    if img and not img.startswith("http"): img = "https:"+img
                    break
            is_pass = False
            best    = None
            for sku in skus:
                sp = (sku.get("Sku") or {}).get("Properties",{})
                if sp.get("IsGamePass") or sp.get("IsMicrosoftGamePass"): is_pass = True
                for av in sku.get("Availabilities",[]):
                    if (av.get("OrderManagementData") or {}).get("SubscriptionData"): is_pass = True
                    pr  = ((av.get("OrderManagementData") or {}).get("Price")) or {}
                    amt = pr.get("ListPrice")
                    if amt and amt > 0 and (best is None or amt < best["amount"]):
                        best = {"amount":amt,"currency":pr.get("CurrencyCode","")}
            result.append({**reg,"amount":best["amount"] if best else None,
                           "currency":best["currency"] if best else None,
                           "title":title,"img":img,"is_pass":is_pass})
        except:
            result.append({**reg,"amount":None,"currency":None,
                           "title":"","img":"","is_pass":False})
    return result

def load_rates():
    try:
        req = urllib.request.Request(
            "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
            headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode()).get("usd",{})
    except:
        return {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass   # silence logs

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if parsed.path == "/api/search":
            q = params.get("q","").strip()
            if not q: return self.send_json({"error":"No query"},400)
            try:    self.send_json(search(q))
            except Exception as e: self.send_json({"error":str(e)},500)

        elif parsed.path == "/api/prices":
            pid = params.get("id","").strip()
            if not pid: return self.send_json({"error":"No id"},400)
            try:
                rows  = prices(pid)
                rates = load_rates()
                title = next((r["title"] for r in rows if r["title"]),"")
                img   = next((r["img"]   for r in rows if r["img"]),"")
                is_pass = any(r["is_pass"] for r in rows)
                enriched = []
                for r in rows:
                    iqd = None
                    usd = None
                    if r["amount"]:
                        if r["currency"]=="USD":
                            usd = r["amount"]
                        else:
                            rate = rates.get((r["currency"] or "").lower())
                            if rate: usd = r["amount"]/rate
                        if usd: iqd = round(usd * IQD)
                    enriched.append({**r,"usd":usd,"iqd":iqd})
                self.send_json({"title":title,"img":img,"is_pass":is_pass,"prices":enriched})
            except Exception as e: self.send_json({"error":str(e)},500)

        else:
            self.send_html(HTML)

# ── Frontend HTML (served at /) ───────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xbox Price Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07090e;--s1:#0d1018;--s2:#131720;--s3:#1a1f2c;
  --b1:rgba(255,255,255,.06);--b2:rgba(255,255,255,.12);
  --green:#00d26a;--gbg:rgba(0,210,106,.10);--gbd:rgba(0,210,106,.25);
  --txt:#edf0f7;--m1:#7e8fa8;--m2:#46526a;
  --gold:#f5c84a;--silver:#a8b8cc;--bronze:#d48040;
  --red:#ff4560;--xbox:#107c10;
  --pass:#52b043;--pbg:rgba(82,176,67,.12);--pbd:rgba(82,176,67,.3);
}
html,body{background:var(--bg);color:var(--txt);font-family:'DM Sans',sans-serif;min-height:100vh;-webkit-font-smoothing:antialiased}
.page{max-width:860px;margin:0 auto;padding:2rem 1rem 5rem}

/* Hero */
.hero{display:flex;align-items:center;gap:14px;margin-bottom:1.8rem}
.logo{width:48px;height:48px;background:var(--xbox);border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 0 28px rgba(16,124,16,.4)}
.logo svg{width:28px;height:28px;fill:#fff}
.htitle{font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;line-height:1}
.htitle span{color:var(--green)}
.hsub{font-size:12px;color:var(--m1);margin-top:4px}

/* Search */
.swrap{position:relative;margin-bottom:.5rem}
.sbar{display:flex;background:var(--s1);border:1px solid var(--b2);border-radius:14px;overflow:hidden;transition:border-color .2s,box-shadow .2s}
.sbar:focus-within{border-color:var(--green);box-shadow:0 0 0 3px rgba(0,210,106,.1)}
.sico{display:flex;align-items:center;padding:0 14px;color:var(--m2)}
.sico svg{width:18px;height:18px}
#qIn{flex:1;background:transparent;border:none;outline:none;font-family:'DM Sans',sans-serif;font-size:15px;color:var(--txt);padding:14px 0;caret-color:var(--green)}
#qIn::placeholder{color:var(--m2)}
#qBtn{background:var(--green);color:#000;border:none;padding:0 22px;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:500;cursor:pointer;display:flex;align-items:center;gap:6px;transition:background .15s;white-space:nowrap}
#qBtn:hover{background:#00e876}
#qBtn:disabled{background:var(--m2);cursor:not-allowed}
#qBtn svg{width:16px;height:16px}
.shint{font-size:11px;color:var(--m2);margin-top:7px;padding-left:2px}

/* Dropdown */
.drop{position:absolute;top:calc(100% + 6px);left:0;right:0;background:var(--s1);border:1px solid var(--b2);border-radius:13px;overflow:hidden;display:none;z-index:100;box-shadow:0 14px 40px rgba(0,0,0,.5);max-height:340px;overflow-y:auto}
.drop.open{display:block}
.ditem{display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--b1);transition:background .1s}
.ditem:last-child{border-bottom:none}
.ditem:hover,.ditem:active{background:var(--s2)}
.dthumb{width:40px;height:40px;border-radius:7px;object-fit:cover;flex-shrink:0;background:var(--s2)}
.dph{width:40px;height:40px;border-radius:7px;background:var(--s2);display:flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--m2)}
.dtxt{flex:1;font-size:13px;font-weight:500}
.darr{color:var(--m2)}
.darr svg{width:14px;height:14px}

/* Status */
.status{text-align:center;padding:3.5rem 1rem;color:var(--m1)}
.status svg.big{width:44px;height:44px;color:var(--m2);margin:0 auto 14px;display:block}
.status p{font-size:14px}
.status.err{color:var(--red)}
.status.err svg.big{color:var(--red)}
.spin{display:inline-block;width:16px;height:16px;border:2px solid var(--b2);border-top-color:var(--green);border-radius:50%;animation:spin .7s linear infinite;vertical-align:-3px;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Game card */
.gcard{display:flex;align-items:center;gap:16px;padding:18px 20px;background:var(--s1);border:1px solid var(--b1);border-radius:14px;margin-bottom:1rem;animation:fi .3s ease}
@keyframes fi{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.gimg{width:64px;height:64px;border-radius:9px;object-fit:cover;flex-shrink:0;background:var(--s2)}
.gname{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;line-height:1.1}
.gmeta{font-size:11px;color:var(--m1);margin-top:4px}
.badges{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}
.badge{display:inline-flex;align-items:center;gap:4px;border-radius:20px;padding:2px 10px;font-size:10px;font-weight:600}
.badge.xbox{background:var(--gbg);color:var(--green);border:1px solid var(--gbd)}
.badge.pass{background:var(--pbg);color:var(--pass);border:1px solid var(--pbd)}
.badge svg{width:10px;height:10px}

/* Price table */
.ptable{background:var(--s1);border:1px solid var(--b1);border-radius:14px;overflow:hidden;animation:fi .3s ease}
.phead{display:grid;grid-template-columns:32px 1fr 100px 140px;padding:10px 16px;border-bottom:1px solid var(--b2);font-size:10px;font-weight:500;color:var(--m2);letter-spacing:.7px;text-transform:uppercase}
.prow{display:grid;grid-template-columns:32px 1fr 100px 140px;padding:14px 16px;border-bottom:1px solid var(--b1);align-items:center;transition:background .12s}
.prow:last-child{border-bottom:none}
.prow:active{background:var(--s2)}
.rank{font-size:13px;font-weight:700;color:var(--m2)}
.rank.g{color:var(--gold)}.rank.s{color:var(--silver)}.rank.b{color:var(--bronze)}
.rcell{display:flex;align-items:center;gap:10px}
.flag{font-size:20px;line-height:1}
.rname{font-size:14px;font-weight:500}
.rcode{font-size:10px;color:var(--m1);margin-top:1px}
.ucol{font-size:12px;color:var(--m1)}
.iqcell{text-align:right}
.iqv{font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;color:var(--txt);line-height:1}
.iqv.best{color:var(--green)}
.iqlbl{font-size:9px;color:var(--m2);letter-spacing:.6px;margin-top:1px}
.unavail{font-size:12px;color:var(--m2);font-style:italic}

/* Banners */
.pbanner,.savebanner{display:flex;align-items:center;gap:10px;margin-top:.9rem;padding:12px 16px;border-radius:11px;font-size:13px;animation:fi .3s ease}
.pbanner{background:var(--pbg);border:1px solid var(--pbd);color:var(--pass)}
.savebanner{background:var(--gbg);border:1px solid var(--gbd);color:var(--green)}
.pbanner strong,.savebanner strong{color:#fff}
.footnote{font-size:10px;color:var(--m2);margin-top:.9rem;padding-left:2px}

/* Skeleton */
.skwrap{background:var(--s1);border:1px solid var(--b1);border-radius:14px;overflow:hidden}
.skrow{display:grid;grid-template-columns:32px 1fr 100px 140px;padding:14px 16px;border-bottom:1px solid var(--b1);align-items:center;gap:10px}
.skrow:last-child{border-bottom:none}
.sk{background:var(--s3);border-radius:5px;animation:pulse 1.3s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.3}50%{opacity:.7}}
</style>
</head>
<body>
<div class="page">

<div class="hero">
  <div class="logo">
    <svg viewBox="0 0 24 24"><path d="M4.102 5.861C3.037 7.32 2.4 9.113 2.4 11.059c0 3.21 1.56 6.058 3.971 7.846C6.925 15.7 9.577 12.087 12 9.509c-2.633-2.478-5.94-3.895-7.898-3.648zm15.796 0C17.94 5.613 14.633 7.03 12 9.51c2.423 2.578 5.075 6.191 5.629 9.396A9.936 9.936 0 0 0 21.6 11.06c0-1.946-.637-3.739-1.702-5.198zM5.98 19.833A9.944 9.944 0 0 0 12 21.6a9.944 9.944 0 0 0 6.02-1.767C17.424 16.65 14.65 13.011 12 10.547c-2.65 2.464-5.424 6.103-6.02 9.286zM12 2.4c-1.768 0-3.42.46-4.853 1.267 2.131-.066 5.476 1.447 8.031 3.799A17.18 17.18 0 0 1 18.853 3.667 9.944 9.944 0 0 0 12 2.4z"/></svg>
  </div>
  <div>
    <div class="htitle">Xbox Price <span>Tracker</span></div>
    <div class="hsub">Live Microsoft Store prices · 12 regions · Iraqi Dinar</div>
  </div>
</div>

<div class="swrap" id="swrap">
  <div class="sbar">
    <span class="sico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg></span>
    <input type="text" id="qIn" placeholder="Search any Xbox game… Halo, GTA V, FIFA…" autocomplete="off">
    <button id="qBtn" onclick="doSearch()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>Search
    </button>
  </div>
  <div class="shint">Live prices from Microsoft Store · $1 = 1,550 IQD</div>
  <div class="drop" id="drop"></div>
</div>

<div id="main" style="margin-top:1.5rem">
  <div class="status">
    <svg class="big" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
    <p>Search any Xbox game to compare live prices in IQD</p>
  </div>
</div>

</div>
<script>
const XBOX = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.102 5.861C3.037 7.32 2.4 9.113 2.4 11.059c0 3.21 1.56 6.058 3.971 7.846C6.925 15.7 9.577 12.087 12 9.509c-2.633-2.478-5.94-3.895-7.898-3.648zm15.796 0C17.94 5.613 14.633 7.03 12 9.51c2.423 2.578 5.075 6.191 5.629 9.396A9.936 9.936 0 0 0 21.6 11.06c0-1.946-.637-3.739-1.702-5.198zM5.98 19.833A9.944 9.944 0 0 0 12 21.6a9.944 9.944 0 0 0 6.02-1.767C17.424 16.65 14.65 13.011 12 10.547c-2.65 2.464-5.424 6.103-6.02 9.286zM12 2.4c-1.768 0-3.42.46-4.853 1.267 2.131-.066 5.476 1.447 8.031 3.799A17.18 17.18 0 0 1 18.853 3.667 9.944 9.944 0 0 0 12 2.4z"/></svg>`
let hits = []

document.getElementById('qIn').addEventListener('keydown', e => { if(e.key==='Enter') doSearch() })
document.addEventListener('click', e => { if(!e.target.closest('#swrap')) closeDrop() })

async function doSearch() {
  const q = document.getElementById('qIn').value.trim()
  if (!q) return
  const btn = document.getElementById('qBtn')
  btn.disabled = true
  btn.innerHTML = '<span class="spin"></span>Searching…'
  closeDrop()
  setMain('<div class="status"><span class="spin"></span><p>Searching Microsoft Store…</p></div>')
  try {
    const res  = await fetch('/api/search?q=' + encodeURIComponent(q))
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    if (!data.length) {
      setMain('<div class="status"><svg class="big" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg><p>No games found. Try a different name.</p></div>')
      return
    }
    hits = data
    data.length === 1 ? loadGame(data[0]) : showDrop(data)
  } catch(e) {
    setMain(`<div class="status err"><svg class="big" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg><p>${esc(e.message)}</p></div>`)
  } finally {
    btn.disabled = false
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>Search'
  }
}

function showDrop(games) {
  const dd = document.getElementById('drop')
  dd.innerHTML = games.map((g,i) => `
    <div class="ditem" onclick="pickGame(${i})">
      ${g.img ? `<img class="dthumb" src="${esc(g.img)}" onerror="this.style.display='none'" loading="lazy">`
               : `<div class="dph">${XBOX}</div>`}
      <div class="dtxt">${esc(g.title)}</div>
      <span class="darr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg></span>
    </div>`).join('')
  dd.classList.add('open')
  setMain('<div class="status"><svg class="big" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18l6-6-6-6"/></svg><p>Pick a game from the list above</p></div>')
}
function pickGame(i) { closeDrop(); loadGame(hits[i]) }
function closeDrop()  { document.getElementById('drop').classList.remove('open') }

async function loadGame(game) {
  setMain(`
    <div class="gcard" style="animation:none">
      ${game.img?`<img class="gimg" src="${esc(game.img)}" onerror="this.style.display='none'">`:''}
      <div><div class="gname">${esc(game.title)}</div><div class="gmeta">Loading prices…</div></div>
    </div>${skeleton()}`)
  try {
    const res  = await fetch('/api/prices?id=' + encodeURIComponent(game.id))
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    render(data, game)
  } catch(e) {
    document.getElementById('priceArea').innerHTML =
      `<div class="status err"><p>${esc(e.message)}</p></div>`
  }
}

function render(data, game) {
  const title = data.title || game.title
  const img   = data.img   || game.img
  const rows  = (data.prices || [])
  const with_ = rows.filter(r => r.iqd).sort((a,b) => a.iqd - b.iqd)
  const no_   = rows.filter(r => !r.iqd)
  const sorted = [...with_, ...no_]
  const minIqd = with_[0]?.iqd
  const usRow  = rows.find(r => r.market === 'US')

  const rankCls = i => i===0?'g':i===1?'s':i===2?'b':''

  const rowsHtml = sorted.map((r,i) => {
    const has   = !!r.iqd
    const cheap = has && r.iqd === minIqd
    const usdFmt = r.usd ? '$'+r.usd.toFixed(2) : '—'
    return `
    <div class="prow">
      <div class="rank ${has?rankCls(i):''}">${has?i+1:'—'}</div>
      <div class="rcell">
        <span class="flag">${r.flag}</span>
        <div><div class="rname">${r.label}</div><div class="rcode">${r.market}</div></div>
      </div>
      <div class="ucol">${usdFmt}</div>
      <div class="iqcell">
        ${has
          ? `<div class="iqv ${cheap?'best':''}">${r.iqd.toLocaleString('en')}</div><div class="iqlbl">IQD</div>`
          : `<span class="unavail">—</span>`}
      </div>
    </div>`
  }).join('')

  const passBanner = data.is_pass
    ? `<div class="pbanner">${XBOX}<span>✅ <strong>Included with Xbox Game Pass</strong></span></div>` : ''

  let saveBanner = ''
  if (with_.length && usRow?.iqd && with_[0].market !== 'US') {
    const saved = usRow.iqd - with_[0].iqd
    if (saved > 0)
      saveBanner = `<div class="savebanner">${XBOX}<span>Buy from <strong>${with_[0].flag} ${with_[0].label}</strong> — save <strong>${saved.toLocaleString('en')} IQD</strong> vs USA</span></div>`
  }

  setMain(`
    <div class="gcard">
      ${img?`<img class="gimg" src="${esc(img)}" onerror="this.style.display='none'">`:''}
      <div>
        <div class="gname">${esc(title)}</div>
        <div class="gmeta">${with_.length} regions with prices · Microsoft Store</div>
        <div class="badges">
          <span class="badge xbox">${XBOX} Xbox</span>
          ${data.is_pass?`<span class="badge pass">${XBOX} Game Pass</span>`:''}
        </div>
      </div>
    </div>
    <div class="ptable">
      <div class="phead"><div>#</div><div>Region</div><div>USD</div><div style="text-align:right">Iraqi Dinar</div></div>
      ${rowsHtml}
    </div>
    ${passBanner}${saveBanner}
    <div class="footnote">Live from Microsoft Store · $1 = 1,550 IQD</div>`)
}

function skeleton() {
  return `<div id="priceArea"><div class="skwrap">${
    [1,2,3,4,5].map(()=>`<div class="skrow">
      <div class="sk" style="width:18px;height:18px;border-radius:50%"></div>
      <div style="display:flex;align-items:center;gap:10px">
        <div class="sk" style="width:26px;height:26px;border-radius:5px"></div>
        <div class="sk" style="width:100px;height:14px"></div>
      </div>
      <div class="sk" style="width:55px;height:14px"></div>
      <div class="sk" style="width:100px;height:20px;margin-left:auto"></div>
    </div>`).join('')}</div></div>`
}
function setMain(h) { document.getElementById('main').innerHTML = h }
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"✅ Xbox Price Tracker running at http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
