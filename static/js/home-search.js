/**
 * Homepage hero search — AI / Product / Lab tabs + autocomplete + navigation
 * Navigates to /search/product/ or /search/lab/ according to Figma flow.
 */
(function () {
  'use strict';

  var PRODUCT_URL =
    (window.HOME_SEARCH && window.HOME_SEARCH.productUrl) ||
    '/api/home/search/products/';
  var LAB_URL =
    (window.HOME_SEARCH && window.HOME_SEARCH.labUrl) ||
    '/api/home/search/labs/';

  function debounce(fn, ms) {
    var t;
    return function () {
      var ctx = this;
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(ctx, args);
      }, ms);
    };
  }

  function hideAllPanels(root) {
    root.querySelectorAll('[data-search-panel]').forEach(function (el) {
      el.hidden = true;
      el.style.display = 'none';
    });
  }

  function showPanel(root, mode) {
    hideAllPanels(root);
    var panel = root.querySelector('[data-search-panel="' + mode + '"]');
    if (panel) {
      panel.hidden = false;
      panel.style.display = '';
    }
  }

  function setActiveTab(tabsRoot, mode) {
    if (!tabsRoot) return;
    tabsRoot.querySelectorAll('.hero__search-tab').forEach(function (btn) {
      var active = btn.getAttribute('data-mode') === mode;
      btn.classList.toggle('hero__search-tab--active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  function switchMode(card, tabs, mode) {
    setActiveTab(tabs, mode);
    showPanel(card, mode);
    var panel = card.querySelector('[data-search-panel="' + mode + '"]');
    if (panel) {
      var input = panel.querySelector('.hero__search-input');
      if (input) {
        setTimeout(function () {
          try { input.focus(); } catch (e) {}
        }, 40);
      }
    }
  }

  function renderDropdown(container, items, onSelect) {
    if (!container) return;
    container.innerHTML = '';
    if (!items || !items.length) {
      container.hidden = true;
      return;
    }

    // Deduplicate on client side by title
    var seenTitles = {};
    var uniqueItems = [];

    items.forEach(function (item) {
      var rawTitle = (item.title || item.lab_name || '').trim();
      var normTitle = rawTitle.toLowerCase();
      if (!seenTitles[normTitle]) {
        seenTitles[normTitle] = true;
        uniqueItems.push(item);
      }
    });

    if (!uniqueItems.length) {
      container.hidden = true;
      return;
    }

    container.hidden = false;
    uniqueItems.forEach(function (item) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'hero-ac__item';
      var title = document.createElement('span');
      title.className = 'hero-ac__title';
      title.textContent = item.title || item.lab_name || '';
      btn.appendChild(title);
      if (item.subtitle) {
        var sub = document.createElement('span');
        sub.className = 'hero-ac__sub';
        sub.textContent = item.subtitle;
        btn.appendChild(sub);
      }
      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        onSelect(item);
      });
      container.appendChild(btn);
    });
  }

  function bindAutocomplete(opts) {
    var input = opts.input;
    var dropdown = opts.dropdown;
    var url = opts.url;
    var onPick = opts.onPick;
    if (!input || !dropdown) return;

    var fetchResults = debounce(function () {
      var q = (input.value || '').trim();
      if (q.length < 2) {
        dropdown.hidden = true;
        dropdown.innerHTML = '';
        return;
      }
      fetch(url + '?q=' + encodeURIComponent(q), {
        headers: { Accept: 'application/json' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var list = (data && data.results) || [];
          renderDropdown(dropdown, list, function (item) {
            input.value = item.title || item.lab_name || '';
            dropdown.hidden = true;
            if (typeof onPick === 'function') onPick(item);
          });
        })
        .catch(function () {
          dropdown.hidden = true;
        });
    }, 260);

    input.addEventListener('input', fetchResults);
    input.addEventListener('focus', fetchResults);
    input.addEventListener('blur', function () {
      setTimeout(function () { dropdown.hidden = true; }, 180);
    });
  }

  function init() {
    var card = document.querySelector('.hero__ai-card');
    if (!card) return;

    var tabs = card.querySelector('.hero__search-tabs');
    if (tabs) {
      tabs.querySelectorAll('.hero__search-tab').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          var mode = btn.getAttribute('data-mode') || 'ai';
          switchMode(card, tabs, mode);
        });
      });
    }

    // Default to 'ai'
    switchMode(card, tabs, 'ai');

    // Autocomplete selection handler for Product Search
    bindAutocomplete({
      input: document.getElementById('heroProductInput'),
      dropdown: document.getElementById('heroProductDropdown'),
      url: PRODUCT_URL,
      onPick: function (item) {
        // Navigates with the distinct product title
        var query = item.title || '';
        window.location.href = '/search/product/?q=' + encodeURIComponent(query);
      },
    });

    // Autocomplete for Lab Search
    bindAutocomplete({
      input: document.getElementById('heroLabInput'),
      dropdown: document.getElementById('heroLabDropdown'),
      url: LAB_URL,
      onPick: function (item) {
        var query = item.title || item.lab_name || '';
        window.location.href = '/search/lab/?q=' + encodeURIComponent(query);
      },
    });

    // Submitting Product Search
    var productInput = document.getElementById('heroProductInput');
    var productBtn = document.getElementById('heroProductBtn');
    function submitProductSearch() {
      var q = (productInput && productInput.value.trim()) || 'HDPE Woven Sacks';
      window.location.href = '/search/product/?q=' + encodeURIComponent(q);
    }
    if (productBtn) productBtn.addEventListener('click', submitProductSearch);
    if (productInput) {
      productInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          submitProductSearch();
        }
      });
    }

    // Submitting Lab Search
    var labInput = document.getElementById('heroLabInput');
    var labBtn = document.getElementById('heroLabBtn');
    function submitLabSearch() {
      var q = (labInput && labInput.value.trim()) || 'Dr. Lal Path Labs';
      window.location.href = '/search/lab/?q=' + encodeURIComponent(q);
    }
    if (labBtn) labBtn.addEventListener('click', submitLabSearch);
    if (labInput) {
      labInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          submitLabSearch();
        }
      });
    }

    // Submitting AI Easy Search
    var aiInput = document.getElementById('heroSearchInput');
    var aiBtn = document.getElementById('heroSearchBtn');
    function submitAiSearch() {
      var q = (aiInput && aiInput.value.trim()) || 'My plastic sacks tear when we fill them with 50 kg of sugar';
      window.location.href = '/search/product/?q=' + encodeURIComponent(q);
    }
    if (aiBtn) aiBtn.addEventListener('click', submitAiSearch);
    if (aiInput) {
      aiInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          submitAiSearch();
        }
      });
    }

    // Chips Navigation
    card.querySelectorAll('.hero__search-chip[data-query]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var query = chip.getAttribute('data-query') || '';
        var panel = chip.closest('[data-search-panel]');
        var panelMode = panel ? panel.getAttribute('data-search-panel') : 'product';

        if (panelMode === 'lab') {
          window.location.href = '/search/lab/?q=' + encodeURIComponent(query);
        } else {
          // Both AI search chips and Product search chips navigate to Product Search Results
          window.location.href = '/search/product/?q=' + encodeURIComponent(query);
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// ####### home card slider ###########
document.addEventListener('DOMContentLoaded', function () {
  const slides = document.querySelectorAll('.hero-domain-card__slide');
  const dots = document.querySelectorAll('.domain-dot');
  if (!slides.length || !dots.length) return;

  let currentSlide = 0;
  let slideInterval;

  function showSlide(index) {
    slides.forEach((slide, i) => {
      slide.classList.toggle('is-active', i === index);
    });
    dots.forEach((dot, i) => {
      dot.classList.toggle('is-active', i === index);
    });
    currentSlide = index;
  }

  function startAutoSlide() {
    slideInterval = setInterval(() => {
      let next = (currentSlide + 1) % slides.length;
      showSlide(next);
    }, 4000);
  }

  dots.forEach((dot) => {
    dot.addEventListener('click', function () {
      clearInterval(slideInterval);
      const index = parseInt(this.getAttribute('data-index'), 10);
      showSlide(index);
      startAutoSlide();
    });
  });

  startAutoSlide();
});