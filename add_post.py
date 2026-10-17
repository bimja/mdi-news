#!/usr/bin/env python3
"""Add a weekly MDI newsletter post to the mdi-news GitHub Pages site.

Usage:
    python3 add_post.py <newsletter_folder> <YYYY-MM-DD> [--title "..."] [--no-hero]

<newsletter_folder> must contain newsletter-public-snippet.html (the PUBLIC-SAFE
version). The internal newsletter files are never read.

The script:
  * cleans the public snippet (drops HTML comments, swaps LOGO_URL_HERE for the
    logo hosted in this repo, sets the "Published" line to the post date),
  * renders a 1200x630 hero image (posts/<date>/hero.png) with headless Chrome,
  * writes posts/<date>/index.html and posts/<date>/content.html,
  * records the post in posts.json (newest first) and regenerates index.html
    and feed.xml (RSS 2.0) from it.
Re-running for the same date replaces that post. Then: git add -A && git commit && git push.
"""
import argparse, datetime as dt, html, json, os, re, shutil, subprocess, sys, tempfile
from email.utils import format_datetime
from zoneinfo import ZoneInfo

SITE_URL = "https://bimja.github.io/mdi-news/"
SITE_TITLE = "MDI & Associates – News"
SITE_DESC = "Weekly project and practice updates from MDI & Associates LLC."
HOME_URL = "https://mdipros.com/news-1"
TZ = ZoneInfo("America/Chicago")
PUB_HOUR = 9  # pubDate time of day (America/Chicago)
ROOT = os.path.dirname(os.path.abspath(__file__))
LOGO_URL = SITE_URL + "assets/mdi-logo.jpg"
NAVY = "#1b2a4a"

def die(msg):
    sys.exit("ERROR: " + msg)

def load_snippet(folder):
    path = os.path.join(folder, "newsletter-public-snippet.html")
    if not os.path.isfile(path):
        die(f"{path} not found (only the PUBLIC-SAFE snippet is used)")
    raw = open(path, encoding="utf-8").read()
    if "PUBLIC-SAFE" not in raw:
        die("snippet lacks the PUBLIC-SAFE marker comment; refusing to publish")
    return raw

def clean_snippet(raw, pub_dt):
    s = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    s = s.replace("LOGO_URL_HERE", LOGO_URL)
    s = re.sub(r"(>)\s*Published [^<]*(<)", lambda m: m.group(1) + "Published " + pub_dt.strftime("%a %b %-d, %Y") + m.group(2), s, count=1)
    if "LOGO_URL_HERE" in s or "{{" in s:
        die("unfilled placeholder left in snippet")
    return s.strip()

def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()

def extract(s):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    headline = text_of(m.group(1)) if m else "MDI Week in Review"
    items = [text_of(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", s, re.S)]
    excerpt = " ".join(items[:2]) if items else headline
    if len(excerpt) > 280:
        excerpt = excerpt[:277].rsplit(" ", 1)[0] + "…"
    return headline, excerpt

def week_title(d):
    monday = d - dt.timedelta(days=d.weekday())
    return f"MDI Weekly Update – Week of {monday.strftime('%b')} {monday.day}, {monday.year}"

def page(title, body, desc, canonical, image=None):
    og_img = f'<meta property="og:image" content="{image}">' if image else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_TITLE)}" href="{SITE_URL}feed.xml">
<link rel="icon" href="{SITE_URL}assets/favicon.png">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">{og_img}
<style>
body{{margin:0;background:#e9ebef;font-family:Arial,Helvetica,sans-serif;color:#2b2b2b}}
.top{{background:{NAVY};color:#fff}} .top .in{{max-width:760px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:12px}}
.top img{{width:40px;height:40px;border-radius:4px}} .top a{{color:#fff;text-decoration:none;font-weight:bold;font-size:18px}}
.top .home{{margin-left:auto;font-weight:normal;font-size:14px;color:#c9d3e6}}
main{{max-width:760px;margin:0 auto;padding:20px}}
.card{{background:#fff;border-radius:8px;border-top:4px solid {NAVY};box-shadow:0 1px 3px rgba(0,0,0,.08);margin:0 0 16px;overflow:hidden;display:flex}}
.card img{{width:220px;object-fit:cover;flex-shrink:0}} .card .tx{{padding:16px 18px}}
.card h2{{margin:0 0 4px;font-size:18px}} .card h2 a{{color:{NAVY};text-decoration:none}}
.card .d{{font-size:13px;color:#6b6b6b;margin-bottom:6px}} .card p{{margin:0;font-size:15px;line-height:1.5}}
footer{{text-align:center;font-size:13px;color:#6b6b6b;padding:20px}} footer a{{color:{NAVY}}}
@media(max-width:560px){{.card{{display:block}}.card img{{width:100%;height:auto}}}}
</style></head><body>
<div class="top"><div class="in"><img src="{SITE_URL}assets/mdi-logo.jpg" alt=""><a href="{SITE_URL}">MDI &amp; Associates News</a><a class="home" href="{HOME_URL}">mdipros.com</a></div></div>
<main>{body}</main>
<footer>MDI &amp; Associates LLC · <a href="{SITE_URL}feed.xml">RSS feed</a></footer>
</body></html>
"""

HERO_TMPL = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:1200px;height:630px;overflow:hidden}
body{background:linear-gradient(135deg,#1b2a4a 0%,#2c4475 100%);font-family:Arial,Helvetica,sans-serif;color:#fff;display:flex;align-items:center}
.l{width:330px;display:flex;justify-content:center} .l img{width:260px;height:260px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.35)}
.r{flex:1;padding:0 64px 0 10px}
.k{font-size:26px;letter-spacing:3px;text-transform:uppercase;color:#c9d3e6}
.t{font-size:58px;font-weight:bold;margin:10px 0 18px;line-height:1.1}
.h{font-size:26px;line-height:1.35;color:#e6ebf5;border-left:5px solid #7fa2e0;padding-left:18px}
.f{position:absolute;bottom:28px;right:64px;font-size:22px;color:#c9d3e6}
</style></head><body><div class="l"><img src="LOGO"></div><div class="r">
<div class="k">MDI Weekly Update</div><div class="t">WEEK</div><div class="h">HEAD</div></div>
<div class="f">MDI &amp; Associates LLC · mdipros.com</div></body></html>"""

def find_chrome():
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(c)
        if p: return p
    return None

def make_hero(out_png, week_label, headline):
    chrome = find_chrome()
    if not chrome:
        return False
    short = headline if len(headline) <= 170 else headline[:167].rsplit(" ", 1)[0] + "…"
    doc = (HERO_TMPL.replace("LOGO", "file://" + os.path.join(ROOT, "assets", "mdi-logo.jpg"))
           .replace("WEEK", html.escape(week_label)).replace("HEAD", html.escape(short)))
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "hero.html"); open(f, "w", encoding="utf-8").write(doc)
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={td}/prof", "--window-size=1200,630",
                        f"--screenshot={out_png}", "file://" + f],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    return os.path.isfile(out_png)

def rss(posts):
    now = format_datetime(dt.datetime.now(TZ))
    items = []
    for p in posts:
        content = open(os.path.join(ROOT, "posts", p["slug"], "content.html"), encoding="utf-8").read()
        content = content.replace("]]>", "]]]]><![CDATA[>")
        img = p["image"]
        items.append(f"""  <item>
    <title>{html.escape(p['title'])}</title>
    <link>{p['url']}</link>
    <guid isPermaLink="true">{p['url']}</guid>
    <pubDate>{p['pubDate']}</pubDate>
    <dc:creator>MDI &amp; Associates LLC</dc:creator>
    <description>{html.escape(p['excerpt'])}</description>
    <content:encoded><![CDATA[<p><img src="{img}" alt="{html.escape(p['title'])}" width="1200"></p>
{content}]]></content:encoded>
    <enclosure url="{img}" length="{p['image_length']}" type="image/png"/>
    <media:content url="{img}" medium="image" type="image/png" width="1200" height="630"/>
    <media:thumbnail url="{img}" width="1200" height="630"/>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>{html.escape(SITE_TITLE)}</title>
  <link>{SITE_URL}</link>
  <atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>
  <description>{html.escape(SITE_DESC)}</description>
  <language>en-us</language>
  <lastBuildDate>{now}</lastBuildDate>
  <image><url>{LOGO_URL}</url><title>{html.escape(SITE_TITLE)}</title><link>{SITE_URL}</link></image>
{chr(10).join(items)}
</channel>
</rss>
"""

def index_html(posts):
    cards = []
    for p in posts:
        cards.append(f"""<div class="card"><a href="{p['url']}"><img src="{p['image']}" alt=""></a><div class="tx">
<h2><a href="{p['url']}">{html.escape(p['title'])}</a></h2><div class="d">{html.escape(p['date_label'])}</div>
<p>{html.escape(p['excerpt'])}</p></div></div>""")
    body = '<h1 style="color:%s;font-size:24px;margin:4px 0 16px">Newsletter</h1>\n' % NAVY + "\n".join(cards or ["<p>No posts yet.</p>"])
    return page(SITE_TITLE, body, SITE_DESC, SITE_URL)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder"); ap.add_argument("date", help="post date YYYY-MM-DD (America/Chicago)")
    ap.add_argument("--title", help="override item title (keep under 65 chars)")
    ap.add_argument("--no-hero", action="store_true", help="reuse assets/default-hero.png instead of rendering")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date)
    pub = dt.datetime(d.year, d.month, d.day, PUB_HOUR, 0, tzinfo=TZ)
    snippet = clean_snippet(load_snippet(a.folder), pub)
    headline, excerpt = extract(snippet)
    title = a.title or week_title(d)
    if len(title) >= 65: die(f"title is {len(title)} chars; keep it under 65")
    slug = d.isoformat()
    pdir = os.path.join(ROOT, "posts", slug); os.makedirs(pdir, exist_ok=True)
    url = f"{SITE_URL}posts/{slug}/"
    hero = os.path.join(pdir, "hero.png")
    monday = d - dt.timedelta(days=d.weekday())
    if a.no_hero or not make_hero(hero, f"Week of {monday.strftime('%b')} {monday.day}, {monday.year}", headline):
        src = os.path.join(ROOT, "assets", "default-hero.png")
        if not os.path.isfile(src): die("could not render hero and assets/default-hero.png is missing")
        shutil.copy(src, hero)
    img_url = url + "hero.png"
    open(os.path.join(pdir, "content.html"), "w", encoding="utf-8").write(snippet + "\n")
    open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(
        page(title, f'<img src="hero.png" alt="" style="width:100%;max-width:720px;display:block;margin:0 auto 16px;border-radius:8px">\n{snippet}', excerpt, url, img_url))
    jpath = os.path.join(ROOT, "posts.json")
    posts = json.load(open(jpath)) if os.path.isfile(jpath) else []
    posts = [p for p in posts if p["slug"] != slug]
    posts.append(dict(slug=slug, title=title, headline=headline, excerpt=excerpt, url=url, image=img_url,
                      image_length=os.path.getsize(hero), pubDate=format_datetime(pub), sort=pub.isoformat(),
                      date_label=pub.strftime("%B %-d, %Y")))
    posts.sort(key=lambda p: p["sort"], reverse=True)
    json.dump(posts, open(jpath, "w"), indent=2, ensure_ascii=False)
    open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8").write(rss(posts))
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(index_html(posts))
    open(os.path.join(ROOT, ".nojekyll"), "a").close()
    print(f"Added: {title}\n  {url}\n  {len(posts)} post(s) in feed. Next: git add -A && git commit -m 'Add {slug} post' && git push")

if __name__ == "__main__":
    main()
