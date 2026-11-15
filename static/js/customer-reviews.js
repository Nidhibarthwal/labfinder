/**
 * Customer reviews tab — edit modal handlers
 */
function openEditModal(reviewId, rating, comment, isAnonymous) {
  const modal = document.getElementById('edit-review-modal');
  const form = document.getElementById('update-review-form');
  if (!modal || !form) return;

  form.action = `/review/${reviewId}/update/`;
  const ratingSelect = document.getElementById('edit-rating-select');
  const commentText = document.getElementById('edit-comment-text');
  const anonCheck = document.getElementById('edit-anonymous-check');

  if (ratingSelect) ratingSelect.value = rating;
  if (commentText) commentText.value = comment;
  if (anonCheck) anonCheck.checked = isAnonymous;

  modal.style.display = 'flex';
}

function closeEditModal() {
  const modal = document.getElementById('edit-review-modal');
  if (modal) modal.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function () {
  const updateForm = document.getElementById('update-review-form');
  if (!updateForm) return;

  updateForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const formData = new FormData(updateForm);
    const submitBtn = document.getElementById('btn-save-review-update');

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    fetch(updateForm.action, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.success) {
          location.reload();
        } else {
          alert(data.message || 'Error updating review.');
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save Changes';
          }
        }
      })
      .catch(function () {
        alert('An error occurred. Please try again.');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Changes';
        }
      });
  });

  // Close modal on backdrop click
  const modal = document.getElementById('edit-review-modal');
  if (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeEditModal();
    });
  }
});
