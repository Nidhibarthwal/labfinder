/**
 * Lab portal — leads search + row/card navigation
 */
document.addEventListener('DOMContentLoaded', function () {
  var q = document.getElementById('lp-lead-search');

  function filterLeads(value) {
    var v = (value || '').toLowerCase().trim();

    // Desktop table rows
    document.querySelectorAll('#lp-lead-table tbody tr').forEach(function (tr) {
      if (tr.classList.contains('lp-empty-row')) return;
      var hay = (tr.getAttribute('data-search') || '').toLowerCase();
      tr.style.display = !v || hay.indexOf(v) !== -1 ? '' : 'none';
    });

    // Mobile cards
    document.querySelectorAll('#lp-lead-cards .lp-lead-card').forEach(function (card) {
      var hay = (card.getAttribute('data-search') || '').toLowerCase();
      card.style.display = !v || hay.indexOf(v) !== -1 ? '' : 'none';
    });
  }

  if (q) {
    q.addEventListener('input', function () {
      filterLeads(q.value);
    });
  }

  function bindNav(selector) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.addEventListener('click', function () {
        var href = el.getAttribute('data-href');
        if (href) window.location.href = href;
      });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          var href = el.getAttribute('data-href');
          if (href) window.location.href = href;
        }
      });
    });
  }

  var orderSearch = document.getElementById('lp-order-search');

  function filterOrders(value) {
    var v = (value || '').toLowerCase().trim();
    document.querySelectorAll('#lp-order-table tbody tr').forEach(function (tr) {
      if (tr.classList.contains('lp-empty-row')) return;
      var hay = (tr.getAttribute('data-search') || '').toLowerCase();
      tr.style.display = !v || hay.indexOf(v) !== -1 ? '' : 'none';
    });
    document.querySelectorAll('#lp-order-cards .lp-lead-card').forEach(function (card) {
      var hay = (card.getAttribute('data-search') || '').toLowerCase();
      card.style.display = !v || hay.indexOf(v) !== -1 ? '' : 'none';
    });
  }

  if (orderSearch) {
    orderSearch.addEventListener('input', function () {
      filterOrders(orderSearch.value);
    });
  }

  var exportBtn = document.getElementById('lp-order-export');
  if (exportBtn) {
    exportBtn.addEventListener('click', function () {
      var lines = [[
        'Order', 'Customer', 'Company', 'Test', 'Value', 'Payment', 'Status', 'Updated', 'Next action'
      ]];
      document.querySelectorAll('#lp-order-table tbody tr').forEach(function (tr) {
        if (tr.classList.contains('lp-empty-row') || tr.style.display === 'none') return;
        lines.push([
          tr.getAttribute('data-order') || '',
          tr.getAttribute('data-customer') || '',
          tr.getAttribute('data-company') || '',
          tr.getAttribute('data-test') || '',
          tr.getAttribute('data-value') || '',
          tr.getAttribute('data-payment') || '',
          tr.getAttribute('data-status') || '',
          tr.getAttribute('data-updated') || '',
          tr.getAttribute('data-next') || ''
        ]);
      });
      var csv = lines.map(function (cols) {
        return cols.map(function (value) {
          var text = String(value).replace(/"/g, '""');
          return '"' + text + '"';
        }).join(',');
      }).join('\n');
      var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      var url = URL.createObjectURL(blob);
      var link = document.createElement('a');
      link.href = url;
      link.download = 'orders.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });
  }

  bindNav('tr[data-href]');
  bindNav('.lp-lead-card[data-href]');
});




document.addEventListener('DOMContentLoaded', function () {
  // Modal toggle elements
  const modal = document.getElementById('reviewModal');
  const openBtns = [
    document.getElementById('openReviewModal'),
    document.getElementById('openReviewModalCard')
  ];
  const closeBtn = document.getElementById('reviewModalClose');
  const backdrop = document.getElementById('reviewModalBackdrop');

  openBtns.forEach(btn => {
    if (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        if (modal) modal.removeAttribute('hidden');
      });
    }
  });

  function closeModal() {
    if (modal) modal.setAttribute('hidden', '');
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (backdrop) backdrop.addEventListener('click', closeModal);

  // Helper function to bind interactive stars to hidden inputs
  function setupStarContainer(container, hiddenInput) {
    if (!container || !hiddenInput) return;
    const stars = container.querySelectorAll('.star, .star-sm');

    function renderState(rating, className) {
      stars.forEach((star, index) => {
        if (index < rating) {
          star.classList.add(className);
        } else {
          star.classList.remove(className);
        }
      });
    }

    stars.forEach(star => {
      // Hover effect
      star.addEventListener('mouseenter', function () {
        const val = parseInt(this.getAttribute('data-val'), 10);
        renderState(val, 'is-hover');
      });

      // Click / Select rating
      star.addEventListener('click', function () {
        const val = parseInt(this.getAttribute('data-val'), 10);
        hiddenInput.value = val;
        renderState(val, 'is-active');
      });
    });

    // Reset to current saved rating on mouse leave
    container.addEventListener('mouseleave', function () {
      stars.forEach(s => s.classList.remove('is-hover'));
      const activeVal = parseInt(hiddenInput.value, 10) || 0;
      renderState(activeVal, 'is-active');
    });
  }

  // Bind Overall Star Group
  setupStarContainer(
    document.getElementById('overallStarGroup'),
    document.getElementById('overallRatingInput')
  );

  // Bind Dynamic Category Star Groups
  const categoryContainers = document.querySelectorAll('.dynamic-category-stars');
  categoryContainers.forEach(container => {
    const targetInputId = container.getAttribute('data-target');
    const hiddenInput = document.getElementById(targetInputId);
    setupStarContainer(container, hiddenInput);
  });
});
