/**
 * Dynamic functionality for Search Results (Product Search & Lab Search)
 * Handles:
 * - Live client-side filtering by Country, Accreditation, Category, Lab Type
 * - Search filter for Country checkboxes ("Type to filter...")
 * - Autocomplete suggestions in top search bar
 * - Tab switching with query preservation
 * - Real-time result count updating & empty states
 */

(function () {
  'use strict';

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

  function initSearchResults() {
    var container = document.querySelector('[data-search-results-page]');
    if (!container) return;

    var pageMode = container.getAttribute('data-search-results-page'); // 'product' or 'lab'
    var searchInput = document.getElementById('topSearchInput');
    var searchBtn = document.getElementById('topSearchBtn');
    var acDropdown = document.getElementById('topSearchDropdown');
    var countryFilterInput = document.getElementById('countryFilterInput');
    var resetFiltersBtn = document.getElementById('resetFiltersBtn');
    var countDisplay = document.getElementById('resultsCountNumber');
    var emptyState = document.getElementById('searchEmptyState');
    var cardsList = document.querySelectorAll('[data-lab-card]');

    var apiUrl =
      pageMode === 'product'
        ? (window.HOME_SEARCH && window.HOME_SEARCH.productUrl) || '/api/home/search/products/'
        : (window.HOME_SEARCH && window.HOME_SEARCH.labUrl) || '/api/home/search/labs/';

    // ------------------------------------------------------------------------
    // 1. Top Search Bar: Autocomplete & Submit
    // ------------------------------------------------------------------------
    if (searchInput && acDropdown) {
      var fetchAC = debounce(function () {
        var q = (searchInput.value || '').trim();
        if (q.length < 2) {
          acDropdown.hidden = true;
          acDropdown.innerHTML = '';
          return;
        }

        fetch(apiUrl + '?q=' + encodeURIComponent(q), {
          headers: { Accept: 'application/json' },
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            var items = (data && data.results) || [];
            if (!items.length) {
              acDropdown.hidden = true;
              return;
            }
            acDropdown.innerHTML = '';
            acDropdown.hidden = false;

            items.forEach(function (item) {
              var btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'search-ac-item';

              var title = document.createElement('span');
              title.className = 'search-ac-item__title';
              title.textContent = item.title || item.lab_name || '';
              btn.appendChild(title);

              if (item.subtitle) {
                var sub = document.createElement('span');
                sub.className = 'search-ac-item__sub';
                sub.textContent = item.subtitle;
                btn.appendChild(sub);
              }

              btn.addEventListener('mousedown', function (e) {
                e.preventDefault();
                searchInput.value = item.title || item.lab_name || '';
                acDropdown.hidden = true;
                doSearch(searchInput.value);
              });

              acDropdown.appendChild(btn);
            });
          })
          .catch(function () {
            acDropdown.hidden = true;
          });
      }, 260);

      searchInput.addEventListener('input', fetchAC);
      searchInput.addEventListener('focus', fetchAC);
      searchInput.addEventListener('blur', function () {
        setTimeout(function () {
          acDropdown.hidden = true;
        }, 180);
      });

      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          doSearch(searchInput.value);
        }
      });
    }

    if (searchBtn) {
      searchBtn.addEventListener('click', function () {
        if (searchInput) {
          doSearch(searchInput.value);
        }
      });
    }

    function doSearch(val) {
      var q = (val || '').trim();
      var targetPath = pageMode === 'lab' ? '/search/lab/' : '/search/product/';
      window.location.href = targetPath + (q ? '?q=' + encodeURIComponent(q) : '');
    }

    // ------------------------------------------------------------------------
    // 2. Filter Search for Country ("Type to filter...")
    // ------------------------------------------------------------------------
    if (countryFilterInput) {
      countryFilterInput.addEventListener(
        'input',
        debounce(function () {
          var term = countryFilterInput.value.toLowerCase().trim();
          var countryItems = document.querySelectorAll('.sidebar-checkbox-item[data-country-item]');
          countryItems.forEach(function (item) {
            var label = (item.getAttribute('data-country-name') || '').toLowerCase();
            if (!term || label.indexOf(term) !== -1) {
              item.style.display = 'flex';
            } else {
              item.style.display = 'none';
            }
          });
        }, 150)
      );
    }

    // ------------------------------------------------------------------------
    // 3. Dynamic DOM Filtering by Checkboxes
    // ------------------------------------------------------------------------
    var checkboxes = document.querySelectorAll('.sidebar-checkbox-item input[type="checkbox"]');

    function applyFilters() {
      var activeCountries = [];
      var activeAccreds = [];
      var activeCategories = [];
      var activeLabTypes = [];

      checkboxes.forEach(function (cb) {
        if (cb.checked) {
          var filterType = cb.getAttribute('data-filter-type');
          var filterVal = (cb.value || '').toLowerCase();
          if (filterType === 'country') activeCountries.push(filterVal);
          if (filterType === 'accreditation') activeAccreds.push(filterVal);
          if (filterType === 'category') activeCategories.push(filterVal);
          if (filterType === 'lab_type') activeLabTypes.push(filterVal);
        }
      });

      // Filter Accreditation options dynamically based strictly on selected country
      var accredItems = document.querySelectorAll('.sidebar-checkbox-item[data-accred-item]');
      accredItems.forEach(function (item) {
        var accredCountry = (item.getAttribute('data-country') || '').toLowerCase().trim();
        // If active countries selected, only show accreditations belonging strictly to those countries
        var isVisible =
          !activeCountries.length ||
          activeCountries.indexOf(accredCountry) !== -1;
        if (isVisible) {
          item.style.display = 'flex';
        } else {
          item.style.display = 'none';
          var cb = item.querySelector('input[type="checkbox"]');
          if (cb && cb.checked) {
            cb.checked = false;
            var valIdx = activeAccreds.indexOf((cb.value || '').toLowerCase());
            if (valIdx !== -1) {
              activeAccreds.splice(valIdx, 1);
            }
          }
        }
      });

      var visibleCount = 0;

      cardsList.forEach(function (card) {
        var cardCountry = (card.getAttribute('data-country') || '').toLowerCase();
        var cardAccreds = (card.getAttribute('data-accreditations') || '').toLowerCase();
        var cardCategories = (card.getAttribute('data-categories') || '').toLowerCase();
        var cardLabType = (card.getAttribute('data-lab-type') || '').toLowerCase();

        var matchCountry =
          !activeCountries.length ||
          activeCountries.some(function (c) {
            return cardCountry.indexOf(c) !== -1;
          });

        var matchAccred =
          !activeAccreds.length ||
          activeAccreds.some(function (a) {
            return cardAccreds.indexOf(a) !== -1;
          });

        var matchCategory =
          !activeCategories.length ||
          activeCategories.some(function (cat) {
            return cardCategories.indexOf(cat) !== -1;
          });

        var matchLabType =
          !activeLabTypes.length ||
          activeLabTypes.some(function (lt) {
            return cardLabType.indexOf(lt) !== -1;
          });

        if (matchCountry && matchAccred && matchCategory && matchLabType) {
          card.style.display = '';
          visibleCount++;
        } else {
          card.style.display = 'none';
        }
      });

      if (countDisplay) {
        countDisplay.textContent = visibleCount;
      }

      if (emptyState) {
        if (visibleCount === 0) {
          emptyState.hidden = false;
          emptyState.style.display = 'block';
        } else {
          emptyState.hidden = true;
          emptyState.style.display = 'none';
        }
      }
    }

    checkboxes.forEach(function (cb) {
      cb.addEventListener('change', applyFilters);
    });

    var sidebar = document.querySelector('.search-sidebar');
    if (sidebar) {
      sidebar.addEventListener('change', applyFilters);
      sidebar.addEventListener('click', function (e) {
        if (e.target.closest('.sidebar-checkbox-item')) {
          setTimeout(applyFilters, 10);
        }
      });
    }

    if (resetFiltersBtn) {
      resetFiltersBtn.addEventListener('click', function (e) {
        e.preventDefault();
        checkboxes.forEach(function (cb) {
          cb.checked = false;
        });
        if (countryFilterInput) countryFilterInput.value = '';
        document
          .querySelectorAll('.sidebar-checkbox-item[data-country-item]')
          .forEach(function (item) {
            item.style.display = 'flex';
          });
        document
          .querySelectorAll('.sidebar-checkbox-item[data-accred-item]')
          .forEach(function (item) {
            item.style.display = 'flex';
          });
        applyFilters();
      });
    }

    // Auto-select country if present in query parameters (e.g. ?country=india)
    var urlParams = new URLSearchParams(window.location.search);
    var urlCountry = (urlParams.get('country') || '').toLowerCase().trim();
    if (urlCountry) {
      checkboxes.forEach(function (cb) {
        if (
          cb.getAttribute('data-filter-type') === 'country' &&
          (cb.value || '').toLowerCase() === urlCountry
        ) {
          cb.checked = true;
        }
      });
    }

    // Trigger initial filter application
    applyFilters();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSearchResults);
  } else {
    initSearchResults();
  }
})();
