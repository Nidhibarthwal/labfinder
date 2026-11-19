/**
 * LabFinder Real-Time SSE Client
 * Connects to the FastAPI gateway and updates DOM elements in real-time
 * when customer reviews are posted, lab replies to reviews, or
 * lab profile / executive summary is updated.
 */

(function (window) {
  'use strict';

  var LabRealtime = {
    source: null,
    branchId: null,
    gatewayUrl: null,

    init: function (options) {
      if (!options || !options.branchId) {
        console.warn('[LabRealtime] branchId is required to start real-time updates.');
        return;
      }

      this.branchId = options.branchId;
      this.gatewayUrl = options.gatewayUrl || window.LABFINDER_REALTIME_URL || (
        window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
          ? 'http://' + window.location.hostname + ':8001'
          : window.location.origin + '/realtime'
      );

      this.connect();
    },

    connect: function () {
      var self = this;
      if (this.source) {
        try { this.source.close(); } catch (e) {}
      }

      var streamUrl = this.gatewayUrl + '/stream/lab/' + this.branchId;
      console.log('[LabRealtime] Connecting to:', streamUrl);

      try {
        this.source = new EventSource(streamUrl);
      } catch (err) {
        console.error('[LabRealtime] Failed to create EventSource:', err);
        return;
      }

      this.source.onopen = function () {
        console.log('[LabRealtime] Connected to lab stream:', self.branchId);
      };

      this.source.onmessage = function (event) {
        if (!event.data || event.data.startsWith(':')) return;

        try {
          var payload = JSON.parse(event.data);
          self.handleEvent(payload);
        } catch (err) {
          console.error('[LabRealtime] Error parsing payload:', err);
        }
      };

      this.source.onerror = function (err) {
        console.warn('[LabRealtime] Stream connection error / disconnected. EventSource will auto-reconnect.', err);
      };
    },

    handleEvent: function (payload) {
      console.log('[LabRealtime] Event received:', payload);

      if (payload.type === 'connected') return;

      // Dispatch global event for custom page handlers
      window.dispatchEvent(new CustomEvent('labfinder:realtime', { detail: payload }));
      console.log('[LabRealtime] Dispatched global event: labfinder:realtime');
      console.log('[LabRealtime] Payload:', payload);
      var table = payload.table;
      console.log('[LabRealtime] Table:', table);

      if (table === 'enquiries_labreview') {
        this.handleReviewEvent(payload);
      } else if (table === 'labs_branch') {
        this.handleBranchUpdate(payload);
      } else if (table === 'labs_branchitem') {
        this.handleScopeUpdate(payload);
      }
    },

    /**
     * Handles new customer reviews (INSERT) as well as review updates/replies (UPDATE).
     */
    handleReviewEvent: function (payload) {
      var review = payload.data;
      if (!review || !review.id) return;

      var action = (payload.action || '').toUpperCase();
      var reviewId = review.id;
      var existingCard = document.querySelector('[data-review-id="' + reviewId + '"]');

      // If it's a new review (INSERT) and not yet in the DOM, prepend it
      if ((action === 'INSERT' || action === 'CREATE' || !existingCard) && !existingCard) {
        this.insertNewReview(review);
      } else {
        this.updateExistingReview(review);
      }
    },

    insertNewReview: function (review) {
      var reviewId = review.id;
      var authorName = review.is_anonymous
        ? 'Anonymous Client'
        : (review.user_name || review.title || 'Verified Client');
      var rating = Math.round(parseFloat(review.overall_rating || 5));
      var summaryText = review.summary || review.title || 'Great laboratory service.';

      // ── 1. Lab Portal: Recent Reviews List (_lp_reviews.html) ─────────────
      var reviewItemsContainer = document.querySelector('.lp-reviews-items');
      if (reviewItemsContainer) {
        // Hide or remove empty state if present
        var emptyState = reviewItemsContainer.querySelector('.lp-reviews-empty');
        if (emptyState) emptyState.style.display = 'none';

        var csrfToken = this.getCsrfToken();
        var card = document.createElement('div');
        card.className = 'lp-review-item';
        card.setAttribute('data-review-id', reviewId);

        // Build Star SVGs
        var starsHtml = '';
        for (var i = 1; i <= 5; i++) {
          var isFilled = i <= rating ? 'is-filled' : 'is-empty';
          starsHtml += '<svg class="lp-star-icon lp-star-icon--sm ' + isFilled + '" viewBox="0 0 20 20" fill="currentColor">' +
            '<path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>' +
            '</svg>';
        }

        card.innerHTML =
          '<div class="lp-review-item__top">' +
            '<span class="lp-review-author">' + this.escapeHtml(authorName) + '</span>' +
            '<span class="lp-review-time">Just now</span>' +
          '</div>' +
          '<div class="lp-review-item__stars">' + starsHtml + '</div>' +
          '<div class="lp-review-text">"' + this.escapeHtml(summaryText) + '"</div>' +
          '<div class="lp-review-reply-action" id="review-reply-action-' + reviewId + '">' +
            '<button type="button" class="lp-btn-reply-toggle" onclick="toggleReviewReplyForm(\'' + reviewId + '\')">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>' +
              ' Reply to this review' +
            '</button>' +
            '<div id="reply-form-' + reviewId + '" class="lp-review-reply-form" style="display: none;">' +
              '<form method="post" action="/enquiry/review/reply/">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrfToken + '">' +
                '<input type="hidden" name="review_id" value="' + reviewId + '">' +
                '<textarea name="reply_message" rows="3" class="lp-textarea" placeholder="Write your professional response..." required></textarea>' +
                '<div style="margin-top: 8px; display: flex; gap: 8px;">' +
                  '<button type="submit" class="lp-btn lp-btn--primary lp-btn--sm">Publish reply</button>' +
                  '<button type="button" class="lp-btn lp-btn--outline lp-btn--sm" onclick="toggleReviewReplyForm(\'' + reviewId + '\')">Cancel</button>' +
                '</div>' +
              '</form>' +
            '</div>' +
          '</div>';

        // Prepend new review card
        reviewItemsContainer.insertBefore(card, reviewItemsContainer.firstChild);
        this.highlightElement(card);
        this.bindReplyFormAjax(card.querySelector('form'));

        // Increment review stats / badge if available
        this.incrementReviewCounters();

        if (typeof window.showSiteToast === 'function') {
          window.showSiteToast('New customer review received from ' + authorName, 'success');
        }
      }

      // ── 2. Customer View: Public Lab Detail (lab-detail.html) ─────────────
      var publicCardsList = document.querySelector('.lp-review-cards-list');
      if (publicCardsList) {
        var pubCard = document.createElement('div');
        pubCard.className = 'lp-rev-card';
        pubCard.setAttribute('data-review-id', reviewId);

        var starStars = '★'.repeat(rating) + '☆'.repeat(5 - rating);
        pubCard.innerHTML =
          '<div>' +
            '<p class="lp-rev-card__body">"' + this.escapeHtml(summaryText) + '"</p>' +
            '<div class="lp-rev-card__stars" style="color:#f59e0b; font-size:14px; margin-top:4px;">' + starStars + '</div>' +
          '</div>' +
          '<div class="lp-rev-card__meta">' +
            '<strong class="lp-rev-card__author">' + this.escapeHtml(authorName) + '</strong>' +
            '<span class="lp-rev-card__date">Just now</span>' +
          '</div>';

        publicCardsList.insertBefore(pubCard, publicCardsList.firstChild);
        this.highlightElement(pubCard);
        this.incrementReviewCounters();
      }
    },

    updateExistingReview: function (review) {
      var reviewId = review.id;
      var replyText = review.lab_reply;

      if (replyText) {
        // 1. Lab Portal: replace action with callout or update existing
        var replyForm = document.getElementById('reply-form-' + reviewId);
        var replyAction = replyForm ? replyForm.closest('.lp-review-reply-action') : document.getElementById('review-reply-action-' + reviewId);
        var existingCalloutText = document.getElementById('review-reply-text-' + reviewId);

        if (existingCalloutText) {
          existingCalloutText.textContent = replyText;
          this.highlightElement(existingCalloutText.closest('.lp-review-reply-callout'));
        } else if (replyAction) {
          var callout = document.createElement('div');
          callout.className = 'lp-review-reply-callout';
          callout.id = 'review-reply-callout-' + reviewId;
          callout.innerHTML =
            '<div class="lp-review-reply-label">Your Reply :</div>' +
            '<div class="lp-review-reply-text" id="review-reply-text-' + reviewId + '">' + this.escapeHtml(replyText) + '</div>';
          replyAction.parentNode.replaceChild(callout, replyAction);
          this.highlightElement(callout);
        }

        // 2. Customer view (_cd_reviews.html)
        var customerReply = document.getElementById('cd-reply-' + reviewId);
        if (customerReply) {
          var p = customerReply.querySelector('p');
          if (p) p.textContent = replyText;
          this.highlightElement(customerReply);
        } else {
          var reviewCard = document.querySelector('[data-review-id="' + reviewId + '"]');
          if (reviewCard) {
            var newReply = document.createElement('div');
            newReply.id = 'cd-reply-' + reviewId;
            newReply.className = 'cd-review-card__reply';
            newReply.innerHTML = '<strong>Lab response:</strong><p>' + this.escapeHtml(replyText) + '</p>';
            reviewCard.appendChild(newReply);
            this.highlightElement(newReply);
          }
        }
      }
    },

    /**
     * Updates executive summary, description, and profile fields in real-time.
     */
    handleBranchUpdate: function (payload) {
      var branch = payload.data;
      if (!branch) return;

      var desc = branch.description !== undefined ? branch.description : branch.about_us;

      // 1. Executive Summary / Description / Overview
      if (desc !== undefined) {
        document.querySelectorAll(
          '.lp-overview-desc, .js-realtime-description, .js-realtime-executive-summary, .js-realtime-about-us'
        ).forEach(function (el) {
          el.textContent = desc || '';
          LabRealtime.highlightElement(el);
        });

        // Update textarea if user is not actively typing in it
        document.querySelectorAll('textarea[name="executive_summary"].js-realtime-input-executive-summary').forEach(function (textarea) {
          if (document.activeElement !== textarea) {
            textarea.value = desc || '';
            LabRealtime.highlightElement(textarea);
          }
        });
      }

      // 2. Minimum Order Value
      if (branch.min_order_value !== undefined) {
        document.querySelectorAll('.js-realtime-min-order, .lp-min-order-val').forEach(function (el) {
          el.textContent = '₹' + branch.min_order_value;
          LabRealtime.highlightElement(el);
        });
      }

      // 3. Lab Name
      if (branch.lab_name !== undefined) {
        document.querySelectorAll('.js-realtime-lab-name, .lp-breadcrumb-current, .lp-detail-hero__title, .lp-modal__lab-name').forEach(function (el) {
          el.textContent = branch.lab_name;
          LabRealtime.highlightElement(el);
        });
        document.querySelectorAll('input[name="legal_lab_name"]').forEach(function (input) {
          if (document.activeElement !== input) {
            input.value = branch.lab_name;
          }
        });
      }

      // 4. Contact Mobile
      if (branch.contact_mobile !== undefined) {
        document.querySelectorAll('.js-realtime-contact-mobile').forEach(function (el) {
          el.textContent = branch.contact_mobile ? ('+91-' + branch.contact_mobile) : '—';
          LabRealtime.highlightElement(el);
        });
        document.querySelectorAll('input[name="phone_number"]').forEach(function (input) {
          if (document.activeElement !== input) {
            input.value = branch.contact_mobile;
          }
        });
      }

      // 5. Contact Email
      if (branch.contact_email !== undefined) {
        document.querySelectorAll('.js-realtime-contact-email').forEach(function (el) {
          el.textContent = branch.contact_email || '—';
          LabRealtime.highlightElement(el);
        });
        document.querySelectorAll('input[name="contact_email"]').forEach(function (input) {
          if (document.activeElement !== input) {
            input.value = branch.contact_email;
          }
        });
      }

      // 6. Facility Address & City & Pincode
      if (branch.lab_address !== undefined || branch.lab_city !== undefined || branch.lab_pincode !== undefined) {
        document.querySelectorAll('.js-realtime-lab-address').forEach(function (el) {
          el.textContent = branch.lab_address || '—';
          LabRealtime.highlightElement(el);
        });
        document.querySelectorAll('.js-realtime-address').forEach(function (el) {
          var parts = [branch.lab_address, branch.lab_city, branch.lab_pincode].filter(Boolean);
          if (parts.length > 0) {
            el.textContent = parts.join(', ');
            LabRealtime.highlightElement(el);
          }
        });
        document.querySelectorAll('.js-realtime-city').forEach(function (el) {
          if (branch.lab_city) {
            el.textContent = branch.lab_city;
            LabRealtime.highlightElement(el);
          }
        });
        document.querySelectorAll('.js-realtime-lab-pincode').forEach(function (el) {
          if (branch.lab_pincode) {
            el.textContent = branch.lab_pincode;
            LabRealtime.highlightElement(el);
          }
        });
      }
    },

    handleScopeUpdate: function (payload) {
      console.log('[LabRealtime] Scope items updated, dispatching refresh event');
      window.dispatchEvent(new CustomEvent('labfinder:scope_update', { detail: payload }));
    },

    incrementReviewCounters: function () {
      document.querySelectorAll(
        '.lp-reviews-header__title, .lp-detail-hero__review-count, .lp-rating-sub'
      ).forEach(function (el) {
        var text = el.textContent;
        var match = text.match(/\((\d+)\)/);
        if (match) {
          var count = parseInt(match[1], 10) + 1;
          el.textContent = text.replace(/\(\d+\)/, '(' + count + ')');
        }
      });
    },

    bindReplyFormAjax: function (form) {
      if (!form) return;
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var submitBtn = form.querySelector('button[type="submit"]');
        var textarea = form.querySelector('textarea');
        var replyText = textarea ? textarea.value.trim() : '';
        if (!replyText) return;

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Publishing...';
        }

        fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data.status === 'success') {
              var actionContainer = form.closest('.lp-review-reply-action');
              if (actionContainer) {
                var callout = document.createElement('div');
                callout.className = 'lp-review-reply-callout';
                callout.innerHTML =
                  '<div class="lp-review-reply-label">Your Reply :</div>' +
                  '<div class="lp-review-reply-text">' + LabRealtime.escapeHtml(data.reply || replyText) + '</div>';
                actionContainer.parentNode.replaceChild(callout, actionContainer);
              }
              if (typeof window.showSiteToast === 'function') {
                window.showSiteToast(data.message || 'Your reply has been published.', 'success');
              }
            } else {
              if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Publish reply';
              }
              if (typeof window.showSiteToast === 'function') {
                window.showSiteToast(data.message || 'Failed to publish reply.', 'error');
              }
            }
          })
          .catch(function () {
            form.submit();
          });
      });
    },

    highlightElement: function (el) {
      if (!el) return;
      el.style.transition = 'background-color 0.4s ease';
      var originalBg = el.style.backgroundColor || '';
      el.style.backgroundColor = '#ecfdf5'; // light emerald pulse
      setTimeout(function () {
        el.style.backgroundColor = originalBg;
      }, 1800);
    },

    getCsrfToken: function () {
      var el = document.querySelector('[name=csrfmiddlewaretoken]');
      if (el) return el.value;
      var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      return match ? decodeURIComponent(match[1]) : '';
    },

    escapeHtml: function (str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },

    disconnect: function () {
      if (this.source) {
        this.source.close();
        this.source = null;
      }
    }
  };

  window.LabRealtime = LabRealtime;
})(window);
