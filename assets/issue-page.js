// Shared behaviour for the five issue deep-dive pages: tabs, sticky tab bar,
// count-ups, publications + news loaders, accordions. Each page loads this
// from inside its BEGIN/END block; scripts/build_squarespace.py inlines it into
// the Squarespace payload.
(function() {
  // Per-page settings live on the root element:
  //   data-category  regex (case-insensitive) matched against Squarespace
  //                  categories — feeds both loadPubs and loadNews
  //   data-pubs      how many publications to list
  const root = document.querySelector('.ha-topic');
  const CATEGORY = new RegExp(root.dataset.category, 'i');
  const PUBS_SHOWN = parseInt(root.dataset.pubs, 10) || 3;

  // ===== Publications loader =====
  function formatDate(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
  }
  function matchesCategory(c) { return CATEGORY.test(c); }

  async function loadPubs() {
    try {
      const r = await fetch('publications.json');
      if (!r.ok) throw new Error('fetch failed');
      const data = await r.json();
      const items = (data.items || []).filter(i =>
        (i.categories || []).some(matchesCategory)
      ).sort((a,b) => (b.publishOn||0) - (a.publishOn||0));

      if (!items.length) return;

      // Vertical list: the most recent publications, first marked "Latest".
      const grid = document.getElementById('ha-topic-pubs');
      grid.innerHTML = items.slice(0, PUBS_SHOWN).map((i, idx) => {
        const url = i.fullUrl ? 'https://hiappleseed.org' + i.fullUrl : '#';
        const img = i.assetUrl ? `${i.assetUrl}?format=300w` : '';
        const badge = idx === 0 ? `<span class="ha-topic__pub-list-badge">Latest</span>` : '';
        return `
          <a class="ha-topic__pub-list-item" href="${url}" target="_blank" rel="noopener">
            <div class="ha-topic__pub-list-thumb">
              ${badge}
              ${img ? `<img src="${img}" alt="">` : ''}
            </div>
            <div class="ha-topic__pub-list-body">
              <div class="ha-topic__pub-list-meta">${formatDate(i.publishOn)}</div>
              <h3 class="ha-topic__pub-list-title">${i.title || 'Untitled'}</h3>
            </div>
          </a>
        `;
      }).join('');
    } catch (e) {
      console.warn('publications.json load failed:', e);
    }
  }

  // ===== News loader (Press & Blog right column) =====
  // Pulls from news.json (auto-synced nightly from hiappleseed.org/blog
  // and hiappleseed.org/in-the-news via scripts/sync-news.py). Renders
  // the newest blog post + newest press mention tagged with this page's
  // issue area into #ha-topic-news-stack. Markup matches the original
  // hardcoded clippings so the existing .ha-topic__news-* CSS applies.
  const NEWS_OUTLET_CODE = {
    'Honolulu Civil Beat':       'CB',
    'Hawaiʻi Public Radio':      'HP',
    'Hawaii Public Radio':       'HP',
    'Honolulu Star-Advertiser':  'SA',
    'PBS Hawaiʻi':               'PB',
    'PBS Hawaii':                'PB',
    'KHON2':                     'KH',
    'Hawaii News Now':           'HN',
  };
  function stripNewsHtml(s) {
    const d = document.createElement('div');
    d.innerHTML = s || '';
    return (d.textContent || d.innerText || '').trim();
  }
  function newsAnchorFor(bio) {
    const name = stripNewsHtml(bio);
    if (NEWS_OUTLET_CODE[name]) return NEWS_OUTLET_CODE[name];
    const words = name.split(/\s+/).filter(Boolean);
    return (words.slice(-2).map(w => w[0]).join('') || 'XX').toUpperCase();
  }
  function newsBlogHtml(b) {
    const author = stripNewsHtml((b.author && b.author.displayName) || '') || 'Hawaiʻi Appleseed';
    const url = b.fullUrl ? 'https://hiappleseed.org' + b.fullUrl : 'https://hiappleseed.org/in-the-news';
    return `
      <article class="ha-topic__news-clipping">
        <div class="ha-topic__news-anchor" aria-hidden="true">HA</div>
        <div class="ha-topic__news-body">
          <div class="ha-topic__news-source">
            <span class="ha-topic__news-source-tag">Blog</span>
            Hawaiʻi Appleseed
          </div>
          <h3 class="ha-topic__news-title">${stripNewsHtml(b.title)}</h3>
          <p class="ha-topic__news-excerpt">${stripNewsHtml(b.excerpt)}</p>
          <div class="ha-topic__news-byline">
            ${formatDate(b.publishOn)}
            <span class="ha-topic__news-byline-sep"></span>
            <strong>${author}</strong>
          </div>
          <a class="ha-topic__news-link" href="${url}" target="_blank" rel="noopener">
            Read the full post
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 7h12M8 2l5 5-5 5"/></svg>
          </a>
        </div>
      </article>`;
  }
  function newsPressHtml(p) {
    const outlet = p.outlet || stripNewsHtml((p.author && p.author.bio) || '') || 'Press';
    const code   = newsAnchorFor(p.outlet || (p.author && p.author.bio) || '');
    const url    = p.sourceUrl || (p.fullUrl ? 'https://hiappleseed.org' + p.fullUrl : '#');
    return `
      <article class="ha-topic__news-clipping">
        <div class="ha-topic__news-anchor ha-topic__news-anchor--press" aria-hidden="true">${code}</div>
        <div class="ha-topic__news-body">
          <div class="ha-topic__news-source">
            <span class="ha-topic__news-source-tag">Press</span>
            ${outlet}
          </div>
          <h3 class="ha-topic__news-title">${stripNewsHtml(p.title)}</h3>
          <p class="ha-topic__news-excerpt">${stripNewsHtml(p.excerpt)}</p>
          <div class="ha-topic__news-byline">
            ${formatDate(p.publishOn)}
            <span class="ha-topic__news-byline-sep"></span>
            <strong>${outlet}</strong>
          </div>
          <a class="ha-topic__news-link" href="${url}" target="_blank" rel="noopener">
            Read on ${outlet}
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 7h12M8 2l5 5-5 5"/></svg>
          </a>
        </div>
      </article>`;
  }
  async function loadNews() {
    try {
      const r = await fetch('news.json');
      if (!r.ok) throw new Error('fetch failed');
      const data = await r.json();
      const pickFirst = items => (items || [])
        .filter(i => (i.categories || []).some(matchesCategory))
        .sort((a,b) => (b.publishOn||0) - (a.publishOn||0))[0];
      const blog  = pickFirst(data.blog);
      const press = pickFirst(data.press);
      const stack = document.getElementById('ha-topic-news-stack');
      if (!stack) return;
      stack.innerHTML = (blog ? newsBlogHtml(blog) : '') + (press ? newsPressHtml(press) : '');
    } catch (e) {
      console.warn('news.json load failed:', e);
    }
  }

  // ===== Tab panel switcher =====
  function initTabs() {
    const tabs = document.querySelectorAll('.ha-topic__tab');
    const stuckTabs = document.querySelectorAll('.ha-topic__stuck-tab');
    const panels = document.querySelectorAll('.ha-topic__panel');
    const indicator = document.querySelector('.ha-topic__tabs-indicator');
    if (!tabs.length || !panels.length) return;

    const VALID_TABS = ['overview', 'priorities'];

    function setTab(name, opts) {
      opts = opts || {};
      if (indicator) indicator.style.opacity = '1';
      tabs.forEach((t, i) => {
        const active = t.dataset.panel === name;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
        if (active && indicator) {
          indicator.style.transform = `translateX(${t.offsetLeft - 4}px)`;
          // Keep the active tab visible when the pill scrolls (mobile)
          const pill = t.parentElement;
          if (pill.scrollWidth > pill.clientWidth) {
            pill.scrollTo({
              left: t.offsetLeft - (pill.clientWidth - t.offsetWidth) / 2,
              behavior: 'smooth'
            });
          }
        }
      });
      // Sync stuck-bar tabs
      stuckTabs.forEach(t => {
        const active = t.dataset.panel === name;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach(p => {
        const active = p.id === `ha-topic-panel-${name}`;
        p.classList.toggle('active', active);
        if (active) p.removeAttribute('hidden');
        else p.setAttribute('hidden', '');
      });
      if (name === 'overview') {
        runCountUps();
      }
      // Update URL hash for deep-linking (unless suppressed)
      if (!opts.silent) {
        const newHash = '#' + name;
        if (location.hash !== newHash) {
          history.replaceState(null, '', newHash);
        }
      }
    }

    // ===== Count-up animation for stat headlines =====
    const countedEls = new WeakSet();
    function runCountUps() {
      document.querySelectorAll('[data-count-to]').forEach(el => {
        if (countedEls.has(el)) return;
        // Only animate if visible (the panel is shown)
        if (!el.offsetParent) return;
        countedEls.add(el);
        const target = parseFloat(el.dataset.countTo);
        const prefix = el.dataset.countPrefix || '';
        const suffix = el.dataset.countSuffix || '';
        const decimals = parseInt(el.dataset.countDecimals || '0', 10);
        const duration = 1400;
        const start = performance.now();
        function frame(now) {
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          const current = (eased * target).toFixed(decimals);
          el.textContent = `${prefix}${current}${suffix}`;
          if (t < 1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
    }

    function closeAll() {
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      stuckTabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      panels.forEach(p => {
        p.classList.remove('active');
        p.setAttribute('hidden', '');
      });
      if (indicator) indicator.style.opacity = '0';
      // Clear hash when all panels closed
      if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    }

    tabs.forEach(t => {
      t.addEventListener('click', () => {
        // Clicking the already-active tab closes the panel
        if (t.classList.contains('active')) {
          closeAll();
        } else {
          setTab(t.dataset.panel);
        }
      });
    });

    // Stuck-bar tab clicks (no-toggle: always set, never close, since the user is already scrolled past)
    stuckTabs.forEach(t => {
      t.addEventListener('click', () => {
        setTab(t.dataset.panel);
        // Scroll to the panel top so the new content is visible
        const panel = document.getElementById('ha-topic-panel-' + t.dataset.panel);
        if (panel) {
          panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });

    // Apply URL hash on load + on hashchange (back/forward navigation)
    function applyHash() {
      const hash = (location.hash || '').replace(/^#/, '');
      if (VALID_TABS.indexOf(hash) !== -1) {
        setTab(hash, { silent: true });
      }
    }
    applyHash();
    // On a fresh load there is usually no #hash, so applyHash() never calls
    // setTab() — yet the default panel is already `active` in the markup. Any
    // one-time init that lives inside setTab (the Chart.js pie, the stat
    // count-ups) therefore never ran. Drive the default tab explicitly.
    const _h = (location.hash || '').replace(/^#/, '');
    if (VALID_TABS.indexOf(_h) === -1) setTab(VALID_TABS[0], { silent: true });
    window.addEventListener('hashchange', applyHash);

    // Re-sync the scrollable tab pill once fonts/layout settle (mobile deep-link)
    window.addEventListener('load', () => {
      const active = document.querySelector('.ha-topic__tab.active');
      if (!active) return;
      const pill = active.parentElement;
      if (pill.scrollWidth > pill.clientWidth) {
        pill.scrollTo({ left: active.offsetLeft - (pill.clientWidth - active.offsetWidth) / 2 });
      }
    });

    // Sticky tab bar: show stuck bar when main tab bar scrolls out
    const stuckBar = document.querySelector('.ha-topic__stuck-bar');
    const mainTabBar = document.querySelector('.ha-topic__tab-bar');
    if (stuckBar && mainTabBar && 'IntersectionObserver' in window) {
      const stickyIO = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          // Show stuck bar when main tab bar is out of view AND scrolled past (above viewport)
          const scrolledPast = e.boundingClientRect.top < 0;
          stuckBar.classList.toggle('is-visible', !e.isIntersecting && scrolledPast);
        });
      }, { threshold: 0, rootMargin: '-80px 0px 0px 0px' });
      stickyIO.observe(mainTabBar);
    }

    // ===== Equity bars + state comparison reveal on scroll-into-view =====
    if ('IntersectionObserver' in window) {
      const revealIO = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add('is-in');
            revealIO.unobserve(e.target);
          }
        });
      }, { threshold: 0.25 });
      ['.ha-topic__bars', '.ha-topic__compare'].forEach(sel => {
        document.querySelectorAll(sel).forEach(el => revealIO.observe(el));
      });
    } else {
      document.querySelectorAll('.ha-topic__bars, .ha-topic__compare').forEach(el => el.classList.add('is-in'));
    }

    document.querySelectorAll('.ha-topic__panel-close').forEach(btn => {
      btn.addEventListener('click', () => {
        closeAll();
        // Scroll smoothly back up to the tab bar
        document.querySelector('.ha-topic__tab-bar').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });

    // Position indicator on initial active tab + window resize
    function positionIndicator() {
      const active = document.querySelector('.ha-topic__tab.active');
      if (active && indicator) {
        indicator.style.transform = `translateX(${active.offsetLeft - 4}px)`;
      }
    }
    // Run after fonts/layout settle
    requestAnimationFrame(() => requestAnimationFrame(positionIndicator));
    window.addEventListener('load', positionIndicator);
    window.addEventListener('resize', positionIndicator);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(positionIndicator);
    }
  }

  // ===== Init =====
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { initTabs(); loadPubs(); loadNews(); });
  } else {
    initTabs(); loadPubs(); loadNews();
  }
})();

// ===== Accordions =====
document.addEventListener('click',function(e){var b=e.target.closest('.ha-acc-btn');if(!b)return;b.setAttribute('aria-expanded',b.getAttribute('aria-expanded')==='true'?'false':'true');});
