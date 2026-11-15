/**
 * Submit review form — auth gate + validation
 */
document.addEventListener('DOMContentLoaded', function () {
  const reviewForm = document.getElementById('reviewForm');
  const btnSubmit = document.getElementById('btnReviewSubmit');

  if (!btnSubmit || !reviewForm) return;

  btnSubmit.addEventListener('click', function (e) {
    e.preventDefault();

    if (!reviewForm.checkValidity()) {
      reviewForm.reportValidity();
      return;
    }

    if (window.GlobalAuth && window.GlobalAuth.isUserAuthenticated) {
      reviewForm.submit();
    } else if (window.GlobalAuth && typeof window.GlobalAuth.openModal === 'function') {
      window.GlobalAuth.openModal(
        'Sign in to Publish Review',
        'Your review details are saved below.',
        function () {
          reviewForm.submit();
        },
        'Customer'
      );
    } else {
      // Fallback submit if GlobalAuth is not available
      reviewForm.submit();
    }
  });
});
