/**
 * autonomous.tw — Card-Based UI Engine
 * Phase 3: Hero Card + Featured Cards + List View + Tag Cloud + Calendar
 *
 * Parses the raw Markdown-rendered HTML and re-renders it into a
 * card-based layout. If the page has no daily-summary structure,
 * leaves the original content intact.
 */
(function () {
  'use strict';

  // ── Constants ──────────────────────────────────────────
  const SCORE_RE = /⭐️\s*(\d+(?:\.\d+)?)\/10/;
  const DOMAIN_TAGS = ['ai-tech', 'taiwan-affairs', 'intl-politics', 'sports', 'knowledge-mgmt'];

  // ── State ───────────────────────────────────────────────
  let allItems = [];
  let activeTag = null;
  let currentLang = 'zh';

  // ── Initialization ─────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    currentLang = detectLanguage();
    const items = parseItemsFromDOM();
    if (items.length === 0) {
      // Not a daily-summary page — leave Cayman rendering as-is
      showLegacyContent();
      return;
    }
    allItems = items;
    hideLegacyContent();
    renderHero(items[0]);
    renderFeatured(items.slice(1, 5));
    renderList(items.slice(5));
    renderTagCloud(items);
    renderCalendar();
    setupLanguageToggle();

    // Re-render on language change
    window.addEventListener('horizon-lang-change', function (e) {
      currentLang = e.detail;
      renderHero(allItems[0]);
      renderFeatured(allItems.slice(1, 5));
      renderList(allItems.slice(5));
    });
  });

  // ── Language Detection ─────────────────────────────────
  function detectLanguage() {
    var saved = null;
    try { saved = localStorage.getItem('horizon-lang'); } catch (e) { /* noop */ }
    return saved === 'en' ? 'en' : 'zh';
  }

  // ── DOM Parsing — extract items from Markdown rendering ─
  function parseItemsFromDOM() {
    var items = [];
    var main = document.querySelector('.main-content');
    if (!main) return items;

    // Find all h2 elements — these are item headers
    var headings = main.querySelectorAll('h2');
    headings.forEach(function (h2) {
      var item = parseItemHeading(h2);
      if (item) items.push(item);
    });

    // Sort by score descending (should already be sorted, but ensure)
    items.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    return items;
  }

  function parseItemHeading(h2) {
    // Format: <a id="item-N"></a> <h2><a href="...">Title</a> ⭐️ N/10</h2>
    var link = h2.querySelector('a[href]');
    if (!link) return null;

    var title = link.textContent.trim();
    var url = link.getAttribute('href') || '';

    var scoreMatch = h2.textContent.match(SCORE_RE);
    var score = scoreMatch ? parseFloat(scoreMatch[1]) : null;

    // Collect siblings until next h2 or hr
    var summary = '', background = '', discussion = '', source = '', tags = [];
    var sibling = h2.nextElementSibling;
    while (sibling) {
      if (sibling.tagName === 'H2' || sibling.tagName === 'HR') break;

      var text = sibling.textContent.trim();

      // Summary: first paragraph after heading
      if (!summary && sibling.tagName === 'P' && !text.startsWith('Source:') && !text.startsWith('來源:') && !text.startsWith('**Tags**') && !text.startsWith('**標籤**') && !text.startsWith('**Background**') && !text.startsWith('**背景**') && !text.startsWith('**Discussion**') && !text.startsWith('**社群討論**')) {
        summary = text;
      }

      // Background
      if (text.startsWith('**Background**') || text.startsWith('**背景**')) {
        background = text.replace(/^\*\*[^*]+\*\*:\s*/, '');
      }

      // Discussion
      if (text.startsWith('**Discussion**') || text.startsWith('**社群討論**')) {
        discussion = text.replace(/^\*\*[^*]+\*\*:\s*/, '');
      }

      // Source line
      if (/^(rss|reddit|github|hackernews|hn|telegram|twitter|openbb|ossinsight|threads)\s*·/i.test(text)) {
        source = text;
      }
      if (/^(來源|source)\s*:/i.test(text)) {
        source = text.replace(/^(來源|source)\s*:\s*/i, '');
      }

      // Tags
      if (text.startsWith('**Tags**') || text.startsWith('**標籤**')) {
        var tagText = text.replace(/^\*\*[^*]+\*\*:\s*/, '');
        var codeSpans = sibling.querySelectorAll('code');
        if (codeSpans.length) {
          codeSpans.forEach(function (c) {
            tags.push(c.textContent.replace(/^#/, '').trim());
          });
        } else {
          tags = tagText.split(/,\s*/).map(function (t) { return t.replace(/`#/g, '').replace(/`/g, '').trim(); }).filter(Boolean);
        }
      }

      sibling = sibling.nextElementSibling;
    }

    return {
      title: title,
      url: url,
      score: score,
      summary: summary,
      background: background,
      discussion: discussion,
      source: source,
      tags: tags,
      element: h2
    };
  }

  // ── Rendering ───────────────────────────────────────────
  function scoreTier(score) {
    if (score >= 9) return 'high';
    if (score >= 7) return 'good';
    if (score >= 5) return 'mid';
    return 'low';
  }

  function renderHero(item) {
    if (!item) return;
    var container = document.getElementById('hz-hero');

    var domainTag = item.tags.find(function (t) { return DOMAIN_TAGS.includes(t); }) || '';
    var heroImage = item.element ? getHeroImage(item) : '';

    container.innerHTML =
      (heroImage ? '<img src="' + escapeAttr(heroImage) + '" alt="" class="hz-hero-image" loading="eager" width="1200" height="630">' : '') +
      '<div class="hz-hero-body">' +
        (domainTag ? '<span class="hz-hero-badge">' + escapeHtml(domainTag) + '</span>' : '') +
        '<h2 class="hz-hero-title"><a href="' + escapeAttr(item.url) + '">' + escapeHtml(item.title) + '</a></h2>' +
        '<div class="hz-hero-score">⭐️ ' + item.score + '/10 — Top Pick</div>' +
        (item.summary ? '<p class="hz-hero-summary">' + escapeHtml(item.summary) + '</p>' : '') +
        (item.background ? '<div class="hz-hero-background">' + escapeHtml(item.background) + '</div>' : '') +
        (item.discussion ? '<div class="hz-hero-discussion">💬 ' + escapeHtml(item.discussion) + '</div>' : '') +
        '<div class="hz-hero-meta">' +
          (item.source ? '<span class="hz-hero-source">' + escapeHtml(item.source) + '</span>' : '') +
          '<div class="hz-hero-tags">' +
            item.tags.map(function (t) {
              return '<span class="hz-tag" data-domain="' + escapeAttr(t) + '">#' + escapeHtml(t) + '</span>';
            }).join('') +
          '</div>' +
        '</div>' +
      '</div>';
    container.style.display = 'block';
  }

  function renderFeatured(items) {
    var container = document.getElementById('hz-featured');
    if (!items || items.length === 0) {
      container.style.display = 'none';
      return;
    }
    container.style.display = 'grid';

    var html = '<h3 class="hz-section-title">📰 重點新聞</h3>';
    items.forEach(function (item) {
      html += renderCard(item);
    });
    container.innerHTML = html;
  }

  function renderCard(item) {
    var thumbImage = getThumbImage(item);
    return (
      '<article class="hz-card">' +
        (thumbImage ? '<img src="' + escapeAttr(thumbImage) + '" alt="" class="hz-card-thumb" loading="lazy" width="400" height="300">' : '') +
        '<div class="hz-card-body">' +
          '<div class="hz-card-header">' +
            '<h3 class="hz-card-title"><a href="' + escapeAttr(item.url) + '">' + escapeHtml(item.title) + '</a></h3>' +
            (item.score !== null ? '<span class="hz-card-score" data-tier="' + scoreTier(item.score) + '">' + item.score + '</span>' : '') +
          '</div>' +
          (item.summary ? '<p class="hz-card-summary">' + escapeHtml(item.summary) + '</p>' : '') +
          '<div class="hz-card-meta">' +
            (item.source ? '<span>' + escapeHtml(item.source) + '</span>' : '') +
            item.tags.slice(0, 3).map(function (t) {
              return '<span class="hz-tag" data-domain="' + escapeAttr(t) + '">#' + escapeHtml(t) + '</span>';
            }).join('') +
          '</div>' +
        '</div>' +
      '</article>'
    );
  }

  function renderList(items) {
    var container = document.getElementById('hz-list');
    if (!items || items.length === 0) {
      container.innerHTML = '';
      return;
    }

    var html = '<h3 class="hz-section-title">📋 更多新聞</h3>';
    items.forEach(function (item) {
      html += (
        '<div class="hz-list-item">' +
          (item.score !== null ? '<span class="hz-list-score" data-tier="' + scoreTier(item.score) + '">' + item.score + '</span>' : '') +
          '<span class="hz-list-title"><a href="' + escapeAttr(item.url) + '">' + escapeHtml(item.title) + '</a></span>' +
          (item.source ? '<span class="hz-list-source">' + escapeHtml(item.source.split('·')[0] || item.source) + '</span>' : '') +
        '</div>'
      );
    });
    container.innerHTML = html;
  }

  // ── Tag Cloud ───────────────────────────────────────────
  function renderTagCloud(items) {
    var container = document.getElementById('hz-tag-cloud');
    var tagCounts = {};
    items.forEach(function (item) {
      (item.tags || []).forEach(function (tag) {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      });
    });

    var sorted = Object.keys(tagCounts).sort(function (a, b) {
      return tagCounts[b] - tagCounts[a];
    });

    var html = '<h4 class="hz-tag-cloud-title">🏷️ ' + (currentLang === 'zh' ? '標籤雲' : 'Tags') + '</h4>';
    html += '<div class="hz-tag-cloud-list">';

    // "All" pill
    html += '<span class="hz-tag-pill' + (activeTag === null ? ' active' : '') + '" data-tag="">' +
      (currentLang === 'zh' ? '全部' : 'All') +
      '<span class="hz-tag-count">' + items.length + '</span></span>';

    sorted.forEach(function (tag) {
      html += '<span class="hz-tag-pill' + (activeTag === tag ? ' active' : '') + '" data-tag="' + escapeAttr(tag) + '">' +
        escapeHtml(tag) + '<span class="hz-tag-count">' + tagCounts[tag] + '</span></span>';
    });
    html += '</div>';
    container.innerHTML = html;

    // Click handlers
    container.querySelectorAll('.hz-tag-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        var tag = this.getAttribute('data-tag') || null;
        activeTag = (tag === activeTag) ? null : tag;
        filterByTag(activeTag);
        renderTagCloud(allItems); // re-render to update active state
        // Re-attach handlers (ugh, but simple enough)
        renderTagCloud(allItems);
      });
    });
  }

  function filterByTag(tag) {
    if (!tag) {
      renderHero(allItems[0]);
      renderFeatured(allItems.slice(1, 5));
      renderList(allItems.slice(5));
      return;
    }

    var filtered = allItems.filter(function (item) {
      return (item.tags || []).indexOf(tag) !== -1;
    });

    if (filtered.length === 0) {
      document.getElementById('hz-hero').innerHTML = '';
      document.getElementById('hz-featured').innerHTML = '';
      document.getElementById('hz-list').innerHTML =
        '<div class="hz-empty"><div class="hz-empty-icon">🔍</div><div class="hz-empty-title">沒有符合的新聞</div></div>';
      return;
    }

    renderHero(filtered[0]);
    renderFeatured(filtered.slice(1, 5));
    renderList(filtered.slice(5));
  }

  // ── Calendar ────────────────────────────────────────────
  function renderCalendar() {
    var container = document.getElementById('hz-calendar');
    var now = new Date();
    var year = now.getFullYear();
    var month = now.getMonth(); // 0-indexed

    // Collect post dates from links on index page (or from data-posts attribute)
    var postDates = collectPostDates();

    var html = '<h4 class="hz-calendar-title">📅 ' + (currentLang === 'zh' ? '日期' : 'Calendar') + '</h4>';

    // Month nav
    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var monthNamesZh = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    var label = currentLang === 'zh' ? (year + '年 ' + monthNamesZh[month]) : (monthNames[month] + ' ' + year);

    html += '<div class="hz-calendar-nav">' +
      '<button id="hz-cal-prev" aria-label="Previous month">&larr;</button>' +
      '<span class="hz-calendar-month">' + label + '</span>' +
      '<button id="hz-cal-next" aria-label="Next month">&rarr;</button>' +
      '</div>';

    // Day of week headers
    var dowZh = ['日','一','二','三','四','五','六'];
    var dowEn = ['Su','Mo','Tu','We','Th','Fr','Sa'];
    html += '<div class="hz-calendar-grid">';
    for (var d = 0; d < 7; d++) {
      html += '<span class="hz-calendar-dow">' + (currentLang === 'zh' ? dowZh[d] : dowEn[d]) + '</span>';
    }

    // Calendar days
    var firstDay = new Date(year, month, 1).getDay();
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var todayStr = now.getFullYear() + '-' + pad(now.getMonth()+1) + '-' + pad(now.getDate());

    // Empty cells before first day
    for (var e = 0; e < firstDay; e++) {
      html += '<span class="hz-calendar-day empty"></span>';
    }

    for (var day = 1; day <= daysInMonth; day++) {
      var dateStr = year + '-' + pad(month+1) + '-' + pad(day);
      var classes = ['hz-calendar-day'];
      if (dateStr === todayStr) classes.push('today');
      if (postDates.indexOf(dateStr) !== -1) classes.push('has-posts');

      html += '<span class="' + classes.join(' ') + '" data-date="' + dateStr + '">' + day + '</span>';
    }

    html += '</div>';
    container.innerHTML = html;

    // Click handler for days with posts
    container.querySelectorAll('.hz-calendar-day.has-posts').forEach(function (dayEl) {
      dayEl.addEventListener('click', function () {
        var date = this.getAttribute('data-date');
        // Navigate to the post for this date
        var link = findPostLink(date);
        if (link) window.location.href = link;
      });
    });
  }

  function collectPostDates() {
    var dates = [];
    // Try to get dates from the page's post list
    var links = document.querySelectorAll('.main-content li a, .lang-section li a');
    links.forEach(function (a) {
      var text = a.textContent.trim();
      // Match YYYY-MM-DD
      var m = text.match(/(\d{4}-\d{2}-\d{2})/);
      if (m) dates.push(m[1]);
    });
    return dates;
  }

  function findPostLink(date) {
    var links = document.querySelectorAll('.main-content a[href], .lang-section a[href]');
    for (var i = 0; i < links.length; i++) {
      if (links[i].textContent.trim().indexOf(date) !== -1) {
        return links[i].getAttribute('href');
      }
    }
    return null;
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  // ── Language Toggle ─────────────────────────────────────
  function setupLanguageToggle() {
    var toggle = document.createElement('div');
    toggle.className = 'lang-toggle';

    var btnEn = document.createElement('button');
    btnEn.textContent = 'EN';
    btnEn.type = 'button';

    var btnZh = document.createElement('button');
    btnZh.textContent = '中文';
    btnZh.type = 'button';

    toggle.appendChild(btnEn);
    toggle.appendChild(btnZh);
    document.body.insertBefore(toggle, document.body.firstChild);

    function updateButtons(lang) {
      if (lang === 'en') {
        btnEn.classList.add('active');
        btnZh.classList.remove('active');
      } else {
        btnZh.classList.add('active');
        btnEn.classList.remove('active');
      }
    }

    function setLang(lang) {
      currentLang = lang;
      updateButtons(lang);
      try { localStorage.setItem('horizon-lang', lang); } catch (e) { /* noop */ }

      // Switch between language versions of the post
      var path = window.location.pathname;
      var target = null;
      if (lang === 'en' && /-zh(?:\.html)?$/.test(path.replace(/\/$/, ''))) {
        target = path.replace(/-zh(\.html)?$/, '-en$1').replace(/-zh\/$/, '-en/');
      } else if (lang === 'zh' && /-en(?:\.html)?$/.test(path.replace(/\/$/, ''))) {
        target = path.replace(/-en(\.html)?$/, '-zh$1').replace(/-en\/$/, '-zh/');
      }

      if (target) {
        window.location.href = target;
      } else {
        // Re-render existing page with new language
        window.dispatchEvent(new CustomEvent('horizon-lang-change', { detail: lang }));
        renderTagCloud(allItems);
        renderCalendar();
      }
    }

    btnEn.addEventListener('click', function () { setLang('en'); });
    btnZh.addEventListener('click', function () { setLang('zh'); });
    updateButtons(currentLang);
  }

  // ── Legacy Content Handling ─────────────────────────────
  function hideLegacyContent() {
    var main = document.querySelector('.main-content');
    if (main) main.style.display = 'none';

    // Hide Cayman header
    var header = document.querySelector('.page-header');
    if (header) header.style.display = 'none';
  }

  function showLegacyContent() {
    // Show everything as-is — Cayman theme handles it
    var main = document.querySelector('.main-content');
    if (main) main.style.display = '';

    // Hide our card containers
    ['hz-hero', 'hz-featured', 'hz-list', 'hz-tag-cloud', 'hz-calendar'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  }

  // ── Utilities ───────────────────────────────────────────
  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /** Extract hero image from item metadata. */
  function getHeroImage(item) {
    // Try data-hero-image attribute on the element first
    if (item.element) {
      var attr = item.element.getAttribute('data-hero-image');
      if (attr) return attr;
    }
    // Fall back to metadata extracted during parsing
    return item.heroImage || '';
  }

  /** Extract thumbnail image from item metadata. */
  function getThumbImage(item) {
    if (item.element) {
      var attr = item.element.getAttribute('data-thumb-image');
      if (attr) return attr;
    }
    return item.thumbImage || '';
  }
})();