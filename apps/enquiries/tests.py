from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.enquiries.models import Enquiry
from apps.labs.models import Branch

User = get_user_model()


class LinkedInSSOAndEnquiryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.lab = Branch.objects.create(
            lab_name="Apex Testing Laboratories",
            lab_city="Mumbai",
        )

    def test_mock_linkedin_login_get_redirects_and_authenticates(self):
        """Mock LinkedIn SSO logs the user in and redirects back to target URL."""
        target_url = f"/enquiry/?lab_id={self.lab.pk}"
        response = self.client.get(f"{reverse('mock-linkedin-login')}?next={target_url}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, target_url)

        # Verify session is authenticated
        user = User.objects.filter(email="linkedin.test@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(user.first_name, "LinkedIn")
        self.assertEqual(user.last_name, "Tester")

    def test_mock_linkedin_login_ajax_post(self):
        """Mock LinkedIn SSO supports AJAX POST and returns JSON."""
        response = self.client.post(
            reverse("mock-linkedin-login"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("provider"), "mock_linkedin")
        self.assertEqual(data.get("user", {}).get("email"), "linkedin.test@example.com")

    def test_enquiry_form_guest_submission_requires_email(self):
        """Guest submission without email fails validation because email is mandatory."""
        response = self.client.post(
            reverse("enquiry_now"),
            {
                "product_name": "Cement Mortar",
                "description": "Compressive testing per IS 4031",
                # email is missing
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_enquiry_form_guest_submission_saves_mandatory_email(self):
        """Guest submission with mandatory email saves successfully with user=None."""
        response = self.client.post(
            reverse("enquiry_now"),
            {
                "product_name": "Drinking Water",
                "description": "Microbiological analysis as per IS 10500",
                "email": "procurement@clientcorp.com",
                "mobile_number": "9876543210",
                "quotation_type": "multiple_labs",
            },
        )
        self.assertEqual(response.status_code, 302)
        enquiry = Enquiry.objects.first()
        self.assertIsNotNone(enquiry)
        self.assertIsNone(enquiry.user)
        self.assertIsNone(enquiry.lab)
        self.assertEqual(enquiry.email, "procurement@clientcorp.com")
        self.assertEqual(enquiry.product_name, "Drinking Water")
        self.assertEqual(enquiry.quotation_type, "multiple_labs")

    def test_enquiry_from_lab_screen_saves_lab_in_enquiry_table(self):
        """When enquiry is submitted for a specific laboratory, enquiry.lab is saved."""
        response = self.client.post(
            reverse("enquiry_now"),
            {
                "lab_id": str(self.lab.pk),
                "quotation_type": "selected_lab",
                "email": "quality@pharma.com",
                "mobile_number": "9123456780",
                "product_name": "Purified Water",
                "description": "Full chemical assays",
            },
        )
        self.assertEqual(response.status_code, 302)
        enquiry = Enquiry.objects.first()
        self.assertIsNotNone(enquiry)
        self.assertEqual(enquiry.lab, self.lab)
        self.assertEqual(enquiry.quotation_type, "selected_lab")
        self.assertEqual(enquiry.email, "quality@pharma.com")

    def test_enquiry_after_linkedin_login_saves_user_and_lab_in_enquiry_table(self):
        """When user logs in via LinkedIn before enquiry, user & lab are saved to Enquiry table."""
        # 1. Login via mock LinkedIn SSO
        login_resp = self.client.get(
            f"{reverse('mock-linkedin-login')}?next=/enquiry/?lab_id={self.lab.pk}"
        )
        self.assertEqual(login_resp.status_code, 302)

        # 2. Submit enquiry as authenticated user (no email field needed)
        response = self.client.post(
            reverse("enquiry_now"),
            {
                "lab_id": str(self.lab.pk),
                "quotation_type": "selected_lab",
                "product_name": "Structural Steel Rebar",
                "description": "Yield tensile strength and bend test",
            },
        )
        self.assertEqual(response.status_code, 302)

        enquiry = Enquiry.objects.first()
        self.assertIsNotNone(enquiry)
        user = User.objects.get(email="linkedin.test@example.com")
        self.assertEqual(enquiry.user, user)
        self.assertEqual(enquiry.lab, self.lab)
        self.assertEqual(enquiry.email, user.email)
        self.assertEqual(enquiry.contact_name, "LinkedIn Tester")
        self.assertEqual(enquiry.product_name, "Structural Steel Rebar")

    def test_lab_detail_page_contains_enquiry_link(self):
        """Lab detail page contains Send Enquiry link with lab_id query parameter."""
        response = self.client.get(reverse("lab-detail", kwargs={"pk": self.lab.pk}))
        self.assertEqual(response.status_code, 200)
        expected_link = f'href="{reverse("enquiry_now")}?lab_id={self.lab.pk}"'
        self.assertIn(expected_link, response.content.decode("utf-8"))
