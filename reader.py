"""Reader view: an in-page overlay rebuilt from the article's text.

Runs in the page itself (never a kite:// page, which can see history). Nodes are rebuilt with createElement and only
href/src/alt survive, so nothing from the page executes; styles use a constructed sheet so strict CSPs allow them.
"""

READER_JS = r"""
(() => {
  const old = document.getElementById('kite-reader');
  if (old) { old.remove(); document.documentElement.style.overflow = ''; return 'off'; }
  const textOf = el => [...el.querySelectorAll('p')].reduce((n, p) => n + p.textContent.trim().length, 0);
  const candidates = [...document.querySelectorAll('article, main, [role=main], .post, .entry-content, .article-body, #content, body')];
  const root = candidates.sort((a, b) => textOf(b) - textOf(a))[0];
  if (!root || textOf(root) < 400) return 'none';

  const KEEP = new Set(['H1','H2','H3','H4','H5','P','UL','OL','LI','BLOCKQUOTE','PRE','CODE','IMG','FIGURE','FIGCAPTION',
                        'A','EM','STRONG','B','I','TABLE','THEAD','TBODY','TR','TD','TH','BR','HR','SUP','SUB']);
  const DROP = new Set(['NAV','ASIDE','FOOTER','HEADER','FORM','SCRIPT','STYLE','NOSCRIPT','IFRAME','BUTTON','SVG',
                        'INPUT','SELECT','TEXTAREA','OBJECT','EMBED','CANVAS','VIDEO','AUDIO','TEMPLATE','DIALOG']);
  const safeUrl = u => /^(https?:|data:image\/)/i.test(u || '') ? u : null;
  const clean = (src, dst) => {
    for (const n of src.childNodes) {
      if (n.nodeType === Node.TEXT_NODE) { dst.appendChild(document.createTextNode(n.textContent)); continue; }
      if (n.nodeType !== Node.ELEMENT_NODE || DROP.has(n.tagName)) continue;
      if (n.getAttribute('aria-hidden') === 'true' || n.hidden) continue;
      if (!KEEP.has(n.tagName)) { clean(n, dst); continue; }
      const el = document.createElement(n.tagName);
      if (n.tagName === 'A' && safeUrl(n.href)) el.href = n.href;
      if (n.tagName === 'IMG') { const s = safeUrl(n.currentSrc || n.src); if (!s) continue; el.src = s; el.alt = n.alt || ''; }
      clean(n, el);
      dst.appendChild(el);
    }
  };

  const host = document.createElement('div');
  host.id = 'kite-reader';
  host.style.cssText = 'position:fixed;inset:0;z-index:2147483647;overflow:auto;';
  const shadow = host.attachShadow({ mode: 'open' });
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    :host { all: initial; }
    .page { min-height:100%; background:#fbf8f3; color:#25221d; font:20px/1.7 Literata, Charter, Georgia, serif; }
    @media (prefers-color-scheme: dark) { .page { background:#1c1f2e; color:#e3e1da; } a { color:#9fb7ff; } }
    article { max-width:68ch; margin:0 auto; padding:72px 28px 120px; }
    h1 { font:700 2.1em/1.15 inherit; margin:0 0 .3em; }
    .site { font:600 14px/1 "Adwaita Sans", system-ui, sans-serif; opacity:.6; margin-bottom:2.2em; }
    h2, h3, h4 { line-height:1.25; margin:1.6em 0 .5em; }
    img { max-width:100%; height:auto; border-radius:8px; display:block; margin:1.2em auto; }
    pre { overflow:auto; font-size:.8em; padding:1em; border-radius:8px; background:rgba(127,127,127,.12); }
    blockquote { margin:1.2em 0; padding-left:1em; border-left:3px solid rgba(127,127,127,.4); font-style:italic; }
    a { color:#2357c4; }
    button { position:fixed; top:16px; right:20px; font:600 14px "Adwaita Sans", system-ui, sans-serif; padding:8px 14px;
      border-radius:999px; border:1px solid rgba(127,127,127,.35); background:inherit; color:inherit; cursor:pointer; }
    button:focus-visible { outline:2px solid #f5b83d; }`);
  shadow.adoptedStyleSheets = [sheet];
  const page = document.createElement('div'); page.className = 'page';
  const exit = document.createElement('button'); exit.textContent = 'Exit reader view';
  exit.onclick = () => { host.remove(); document.documentElement.style.overflow = ''; };
  const article = document.createElement('article');
  const h1 = document.createElement('h1');
  h1.textContent = (root.querySelector('h1') || document.querySelector('h1') || {}).textContent?.trim() || document.title;
  const site = document.createElement('div'); site.className = 'site'; site.textContent = location.hostname;
  article.append(h1, site);
  clean(root, article);
  for (const dup of article.querySelectorAll('h1')) if (dup !== h1 && dup.textContent.trim() === h1.textContent) dup.remove();
  page.append(exit, article);
  shadow.appendChild(page);
  document.documentElement.appendChild(host);
  document.documentElement.style.overflow = 'hidden';
  host.scrollTop = 0;
  return 'on';
})()
"""
