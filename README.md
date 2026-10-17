# MDI & Associates – News feed

Public RSS feed and mini-site for the MDI weekly newsletter, published with GitHub Pages and shown on
https://mdipros.com/news-1 through a GoDaddy Blog section set to **External blog feed**.

- Site: https://bimja.github.io/mdi-news/
- Feed: https://bimja.github.io/mdi-news/feed.xml

**Public content only.** `add_post.py` reads only `newsletter-public-snippet.html` (it refuses a file without the
`PUBLIC-SAFE` marker). Never copy the internal newsletter (`newsletter.html`, `newsletter-snippet.html`,
`preview.png`) into this repo.

## Weekly update

```bash
cd /workspace/mdi-news
python3 add_post.py /workspace/newsletter/2026-10-23 2026-10-23
git add -A && git commit -m "Add 2026-10-23 post" && git push
```

- Arg 1: newsletter folder containing `newsletter-public-snippet.html`.
- Arg 2: post date `YYYY-MM-DD`; pubDate is 9:00 AM America/Chicago that day. The item title becomes
  `MDI Weekly Update – Week of <Monday of that week>`. Override with `--title "..."` (must be under 65 chars).
- The script removes HTML comments, swaps `LOGO_URL_HERE` for `assets/mdi-logo.jpg`, sets the "Published" line to
  the post date, renders `posts/<date>/hero.png` (1200x630) with headless Chrome (`--no-hero` reuses
  `assets/default-hero.png`), writes `posts/<date>/index.html`, and regenerates `index.html` and `feed.xml`
  (newest first) from `posts.json`. Re-running the same date replaces that post.
- GitHub Pages republishes about a minute after the push. GoDaddy picks up the feed on its own refresh schedule.

## Layout
`index.html` post list · `posts/<date>/` post page, content and hero · `feed.xml` RSS 2.0 (content:encoded, enclosure,
media:content) · `posts.json` post index · `assets/` logo, favicon and fallback hero · `.nojekyll`.
