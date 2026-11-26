from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from apps.accounts.models import OTPVerification
from apps.labs.models import Branch
from apps.utility.models import Country, State

User = get_user_model()


class LabSlugAndDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.lab1 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Ghaziabad",
            is_active=True,
            is_public=True,
        )

    def test_slug_auto_generation_on_save(self):
        """Branch automatically generates an SEO slug on save based on lab_name."""
        self.assertEqual(self.lab1.slug, "ghaziabad-testing-lab")
        self.assertEqual(self.lab1.get_absolute_url(), "/lab-detail/ghaziabad-testing-lab/")

    def test_slug_uniqueness_handles_collisions(self):
        """Creating labs with identical names distinguishes them by city or counter."""
        lab2 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Noida",
            is_active=True,
            is_public=True,
        )
        self.assertEqual(lab2.slug, "ghaziabad-testing-lab-noida")

        lab3 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Noida",
            is_active=True,
            is_public=True,
        )
        self.assertEqual(lab3.slug, "ghaziabad-testing-lab-noida-2")

    def test_lab_detail_view_resolves_by_slug(self):
        """Accessing /lab-detail/<slug>/ returns 200 OK with the lab page."""
        response = self.client.get(f"/lab-detail/{self.lab1.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ghaziabad Testing Lab")

    def test_lab_detail_view_redirects_uuid_to_slug(self):
        """Accessing /lab-detail/<uuid>/ returns 301 Permanent Redirect to /lab-detail/<slug>/."""
        response = self.client.get(f"/lab-detail/{self.lab1.pk}/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, self.lab1.get_absolute_url())

        # Following redirect leads to 200 OK page
        follow_response = self.client.get(f"/lab-detail/{self.lab1.pk}/", follow=True)
        self.assertEqual(follow_response.status_code, 200)
        self.assertContains(follow_response, "Ghaziabad Testing Lab")

    def test_sitemap_labs_uses_slug_urls(self):
        """The /sitemap-labs.xml sitemap outputs SEO slug URLs."""
        response = self.client.get(reverse("django.contrib.sitemaps.views.sitemap", kwargs={"section": "labs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/lab-detail/{self.lab1.slug}/")

    def test_other_labs_prefers_same_city_then_falls_back_to_same_state(self):
        """Other Labs shows same-city labs first, and falls back to same-state labs if none match city."""
        country_in = Country.objects.create(name="India")
        state_up = State.objects.create(name="Uttar Pradesh", country=country_in)
        state_mh = State.objects.create(name="Maharashtra", country=country_in)

        self.lab1.lab_state = state_up
        self.lab1.save()

        same_city_lab = Branch.objects.create(
            lab_name="Apex Ghaziabad Lab",
            lab_city="ghaziabad",
            lab_state=state_up,
            is_active=True,
            is_public=True,
        )
        same_state_lab = Branch.objects.create(
            lab_name="Noida Quality Lab",
            lab_city="Noida",
            lab_state=state_up,
            is_active=True,
            is_public=True,
        )
        other_state_lab = Branch.objects.create(
            lab_name="Mumbai Testing Lab",
            lab_city="Mumbai",
            lab_state=state_mh,
            is_active=True,
            is_public=True,
        )

        # 1. When another lab exists in the same city, only same-city labs are returned
        response = self.client.get(self.lab1.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        other_labs = list(response.context["other_labs"])
        self.assertEqual(other_labs, [same_city_lab])

        # 2. When no other lab exists in the same city, fall back to same-state labs
        response_fallback = self.client.get(same_state_lab.get_absolute_url())
        self.assertEqual(response_fallback.status_code, 200)
        fallback_labs = list(response_fallback.context["other_labs"])
        self.assertIn(self.lab1, fallback_labs)
        self.assertIn(same_city_lab, fallback_labs)
        self.assertNotIn(other_state_lab, fallback_labs)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="http://localhost:8001",
)
class ClaimProfileEmailAndOTPFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_tester",
            email="admin@labfinder360.com",
            password="AdminPassword123!",
        )
        self.country = Country.objects.create(name="India")
        self.state = State.objects.create(name="Gujarat", country=self.country)
        self.lab_unsent = Branch.objects.create(
            lab_name="Meridian Analytical Labs",
            contact_person="Palak Pitroda",
            contact_email="palak@meridianlabs.com",
            lab_city="Surat",
            lab_state=self.state,
            lab_country=self.country,
            lab_pincode="395505",
            claim_email_sent=False,
        )
        self.lab_already_sent = Branch.objects.create(
            lab_name="Already Notified Lab",
            contact_email="already@notified.com",
            claim_email_sent=True,
        )
        self.lab_no_email = Branch.objects.create(
            lab_name="No Email Lab",
            contact_email="",
            claim_email_sent=False,
        )

    def test_admin_changelist_has_send_claim_profile_email_button_and_sends_emails(self):
        """Admin changelist shows Send Claim Profile Email button and sends only to unsent labs with email."""
        self.client.force_login(self.admin_user)
        changelist_url = reverse("admin:labs_branch_changelist")
        res = self.client.get(changelist_url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Send Claim Profile Email")

        # Click Send Claim Profile Email for ALL unsent labs
        send_url = reverse("admin:labs_branch_send_claim_email")
        post_res = self.client.post(send_url, follow=True)
        self.assertEqual(post_res.status_code, 200)

        # Only lab_unsent should receive the email
        self.assertEqual(len(mail.outbox), 1)
        sent_msg = mail.outbox[0]
        self.assertEqual(sent_msg.to, ["palak@meridianlabs.com"])
        self.assertIn("Meridian Analytical Labs", sent_msg.subject)

        html_body = sent_msg.alternatives[0][0]
        self.assertIn("CLAIM YOUR LAB", html_body)
        self.assertIn("http://localhost:8001/register/", html_body)
        self.assertIn("Hello Palak Pitroda", html_body)
        self.assertIn("UNCLAIMED LISTING", html_body)

        self.lab_unsent.refresh_from_db()
        self.assertTrue(self.lab_unsent.claim_email_sent)
        self.assertIsNotNone(self.lab_unsent.claim_email_sent_at)

    def test_register_otp_verify_marks_claimed_and_routes_via_get_redirect_url(self):
        """When claim email was sent to Branch.contact_email, OTP verification marks Branch.status='claimed', sends Badge email, and redirects via get_redirect_url (/lab-review-detail/)."""
        # Mark claim email as sent first
        self.lab_unsent.claim_email_sent = True
        self.lab_unsent.save(update_fields=["claim_email_sent"])

        # 1. Submit email on /register/
        reg_res = self.client.post(
            reverse("register"),
            {"email": "palak@meridianlabs.com"},
        )
        self.assertEqual(reg_res.status_code, 200)
        reg_data = reg_res.json()
        self.assertTrue(reg_data["success"])
        self.assertEqual(reg_data["redirect_to"], "/verify-email/")

        # OTP email sent using OTP.png template
        self.assertEqual(len(mail.outbox), 1)
        otp_email = mail.outbox[0]
        self.assertEqual(otp_email.to, ["palak@meridianlabs.com"])
        otp_html = otp_email.alternatives[0][0]
        self.assertIn("ONE-TIME PASSCODE", otp_html)
        self.assertIn("Verify your email address", otp_html)

        otp_record = OTPVerification.objects.filter(
            email="palak@meridianlabs.com",
            status=OTPVerification.Status.ACTIVE,
        ).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp_code), 5)
        self.assertIn(otp_record.otp_code, otp_html)

        # 2. Verify OTP on /verify-email/
        verify_res = self.client.post(
            reverse("verify_email"),
            {"otp": otp_record.otp_code},
        )
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.json()
        self.assertTrue(verify_data["success"])
        self.assertEqual(verify_data["redirect_url"], reverse("lab-review-detail"))

        # Branch status is now 'claimed'
        self.lab_unsent.refresh_from_db()
        self.assertEqual(self.lab_unsent.status, "claimed")

        # 3. Verified Lab Badge registration success email sent (Badge.png template)
        self.assertEqual(len(mail.outbox), 2)
        badge_email = mail.outbox[1]
        self.assertEqual(badge_email.to, ["palak@meridianlabs.com"])
        badge_html = badge_email.alternatives[0][0]
        self.assertIn("ACHIEVEMENT UNLOCKED", badge_html)
        self.assertIn("Meridian Analytical Labs is now officially verified.", badge_html)
        self.assertIn("GET YOUR WEBSITE BADGE", badge_html)
        self.assertIn("QUICK EMBED CODE PREVIEW", badge_html)


