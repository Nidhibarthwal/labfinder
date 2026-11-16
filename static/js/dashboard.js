/* ==========================================================
   dashboard.js — shared JS for LabFinder dashboard pages
   ========================================================== */

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — Tab switching                                        */
/* ------------------------------------------------------------------ */
function odTab(btn, pane) {
  document.querySelectorAll('.od-tab').forEach(function (t) { t.classList.remove('active'); });
  document.querySelectorAll('.od-tab-content').forEach(function (p) { p.classList.remove('active'); });
  btn.classList.add('active');
  var el = document.getElementById('pane-' + pane);
  if (el) { el.classList.add('active'); }
  if (pane === 'chat') { odScrollChatToBottom(); }
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — Chat helpers                                         */
/* ------------------------------------------------------------------ */
function odScrollChatToBottom() {
  var c = document.getElementById('odChatMsgs');
  if (c) { c.scrollTop = c.scrollHeight; }
}

function odQuickReply(text) {
  var ta = document.getElementById('odMsgInput');
  if (ta) {
    ta.value = text;
    ta.focus();
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }
  var chatBtn = document.getElementById('tab-chat');
  if (chatBtn) { odTab(chatBtn, 'chat'); }
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — File attach display                                  */
/* ------------------------------------------------------------------ */
function odInitAttach() {
  var odAttach = document.getElementById('odAttach');
  if (odAttach) {
    odAttach.addEventListener('change', function () {
      var d = document.getElementById('odAttachDisplay');
      if (d) {
        if (this.files.length) {
          d.style.display = 'block';
          d.textContent = '\uD83D\uDCCE ' + this.files[0].name;
        } else {
          d.style.display = 'none';
        }
      }
    });
  }
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — Upload toggle                                        */
/* ------------------------------------------------------------------ */
function odShowDocUpload() {
  var upload = document.getElementById('odDocUpload');
  var btn = document.getElementById('odUploadBtn');
  if (upload) { upload.style.display = 'block'; }
  if (btn) { btn.style.display = 'none'; }
}

function odHideDocUpload() {
  var upload = document.getElementById('odDocUpload');
  var btn = document.getElementById('odUploadBtn');
  if (upload) { upload.style.display = 'none'; }
  if (btn) { btn.style.display = ''; }
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — Flash dismiss                                        */
/* ------------------------------------------------------------------ */
function odInitFlash() {
  setTimeout(function () {
    var f = document.getElementById('odFlash');
    if (f) {
      f.style.opacity = '0';
      f.style.transition = 'opacity .4s';
      setTimeout(function () { if (f && f.parentNode) { f.parentNode.removeChild(f); } }, 400);
    }
  }, 5000);
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — Open active tab on query param or hash              */
/* ------------------------------------------------------------------ */
function odCheckActiveTab() {
  var params = new URLSearchParams(window.location.search);
  var subtab = params.get('subtab') || (window.location.hash ? window.location.hash.replace('#', '') : null);
  if (subtab) {
    if (subtab === 'documents') subtab = 'docs';
    if (subtab === 'payments') subtab = 'qi';
    var btn = document.getElementById('tab-' + subtab);
    if (btn) {
      odTab(btn, subtab);
      return;
    }
  }
  if (window.location.hash === '#dispute') {
    var disputeBtn = document.getElementById('tab-dispute');
    if (disputeBtn) { odTab(disputeBtn, 'dispute'); }
  }
}

/* ------------------------------------------------------------------ */
/*  ORDER DETAIL — DOMContentLoaded initialisation                      */
/* ------------------------------------------------------------------ */
document.addEventListener('DOMContentLoaded', function () {
  /* Only run on pages that have order detail elements */
  if (!document.querySelector('.od-wrap')) { return; }

  odScrollChatToBottom();
  odInitAttach();
  odInitFlash();
  odCheckActiveTab();
});
