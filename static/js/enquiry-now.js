/**
 * Enquiry Now – interactive chips, tabs, guest auth bridge
 */
(function () {
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function setActivePill(group, value) {
    qsa('[data-pill-group="' + group + '"]').forEach(function (el) {
      el.classList.toggle('is-active', el.getAttribute('data-value') === value);
    });
  }

  function initPills() {
    var customBudget = qs('#id_custom_budget');
    qsa('[data-pill-group]').forEach(function (pill) {
      pill.addEventListener('click', function () {
        var group = pill.getAttribute('data-pill-group');
        var value = pill.getAttribute('data-value');
        setActivePill(group, value);
        var target = qs('[data-pill-target="' + group + '"]');
        if (target) {
          target.value = value;
          target.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (group === 'budget' && customBudget) {
          customBudget.value = '';
        }
      });
    });

    if (customBudget) {
      customBudget.addEventListener('input', function () {
        var val = customBudget.value.trim();
        var target = qs('[data-pill-target="budget"]');
        if (val) {
          qsa('[data-pill-group="budget"]').forEach(function (el) {
            el.classList.remove('is-active');
          });
          var formatted = val.startsWith('₹') ? val : ('₹' + val);
          if (target) {
            target.value = formatted;
            target.dispatchEvent(new Event('change', { bubbles: true }));
          }
        } else {
          setActivePill('budget', '');
          if (target) {
            target.value = '';
            target.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }
      });
    }
  }

  function initOptions() {
    qsa('.enq-option').forEach(function (opt) {
      opt.addEventListener('click', function (e) {
        if (e.target.tagName === 'INPUT') return;
        var input = qs('input[type="radio"]', opt);
        if (input) {
          input.checked = true;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
      var input = qs('input[type="radio"]', opt);
      if (input) {
        var sync = function () {
          qsa('.enq-option[data-option-group="' + opt.getAttribute('data-option-group') + '"]').forEach(function (o) {
            o.classList.toggle('is-selected', qs('input', o).checked);
          });
        };
        input.addEventListener('change', sync);
        sync();
      }
    });
  }

  function initTabs() {
    qsa('[data-enq-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var name = tab.getAttribute('data-enq-tab');
        qsa('[data-enq-tab]').forEach(function (t) {
          t.classList.toggle('is-active', t === tab);
        });
        qsa('[data-enq-panel]').forEach(function (p) {
          p.classList.toggle('is-active', p.getAttribute('data-enq-panel') === name);
        });
      });
    });
  }

  function initTermsGate() {
    var terms = qs('#enq-terms');
    var submitBtns = qsa('[data-enq-submit]');
    function sync() {
      var ok = !terms || terms.checked;
      submitBtns.forEach(function (b) { b.disabled = !ok; });
      var side = qs('#enq-sidebar-submit');
      if (side) {
        side.classList.toggle('is-ready', ok);
        side.disabled = !ok;
      }
    }
    if (terms) {
      terms.addEventListener('change', sync);
      sync();
    }
  }

  function initSidebarSubmit() {
    var side = qs('#enq-sidebar-submit');
    var main = qs('#enq-main-submit') || qs('[data-enq-submit="main"]');
    if (side && main) {
      side.addEventListener('click', function (e) {
        e.preventDefault();
        if (side.disabled) return;
        // Prefer main form submit trigger (handles guest modal)
        if (main.tagName === 'BUTTON') {
          main.click();
        } else {
          var form = qs('#main-enquiry-form') || qs('.enq-form');
          if (form) form.requestSubmit ? form.requestSubmit() : form.submit();
        }
      });
    }
  }

  function initCatalogRemove() {
    qsa('[data-remove-service]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var chip = btn.closest('.enq-chip-selected');
        if (chip) chip.remove();
        var hidden = qs('#id_preferred_services');
        if (hidden) hidden.value = '';
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.body.classList.add('enquiry-now-page');
    initPills();
    initOptions();
    initTabs();
    initTermsGate();
    initSidebarSubmit();
    initCatalogRemove();

    // Sign In / Sign up → global auth modal
    function openAuth(mode) {
      if (window.GlobalAuth && typeof window.GlobalAuth.openModal === 'function') {
        window.GlobalAuth.openModal(null, null, null, 'Customer', mode || 'login');
        return true;
      }
      var modal = document.getElementById('authPromptModal');
      if (modal) {
        modal.classList.add('is-open');
        modal.style.display = 'flex';
        return true;
      }
      console.warn('Auth modal not available');
      return false;
    }
    var signIn = document.getElementById('enq-btn-signin');
    if (signIn) {
      signIn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openAuth('login');
      });
    }
    document.querySelectorAll('[data-open-auth]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        openAuth(el.getAttribute('data-open-auth') || 'login');
      });
    });
  });
})();
