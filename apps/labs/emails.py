import logging
from email.mime.image import MIMEImage
from pathlib import Path
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_html_email_with_inline_images(subject, text_body, html_body, recipient, inline_images=None):
    """
    Sends a multipart/related email wrapping multipart/alternative (text + html)
    and inline CID images with Content-ID + X-Attachment-Id and NO Content-Disposition,
    so Gmail and Outlook display images inline only without showing a 'noname' attachment.
    """
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    msg.attach_alternative(html_body, "text/html")

    if inline_images:
        msg.mixed_subtype = "related"
        for relative_static_path, cid in inline_images:
            file_path = Path(settings.BASE_DIR) / relative_static_path
            if not file_path.is_file():
                logger.warning("Inline email image not found: %s", file_path)
                continue
            with open(file_path, "rb") as img_file:
                mime_img = MIMEImage(img_file.read())
                mime_img.add_header("Content-ID", f"<{cid}>")
                mime_img.add_header("X-Attachment-Id", cid)
                msg.attach(mime_img)

    msg.send(fail_silently=False)
    return msg


def _get_site_base_url(base_url=None):
    if base_url:
        return base_url.rstrip("/")
    return (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")


def _get_public_source(branch=None):
    if branch:
        source = (getattr(branch, "source", "") or "").lower()
        if source == "nabl" or getattr(branch, "NABL_code", None):
            return "NABL Public Directory"
        if source == "bis" or getattr(branch, "BIS_code", None):
            return "BIS Public Directory"
    return "NABL / BIS Public Directory"


def _format_branch_location(branch):
    parts = []
    if branch.lab_city:
        parts.append(branch.lab_city.strip())
    if branch.lab_state:
        parts.append(branch.lab_state.name)
    if branch.lab_country:
        parts.append(branch.lab_country.name)
    location = ", ".join(parts)
    if branch.lab_pincode:
        location = f"{location} {branch.lab_pincode}".strip()
    return location


def _get_branch_category_tags(branch):
    tags = list(branch.categories.values_list("name", flat=True)[:4])
    if not tags and branch.group_name:
        tags = [g.strip() for g in branch.group_name.split(",") if g.strip()][:4]
    if not tags and branch.discipline_name:
        tags = [d.strip() for d in branch.discipline_name.split(",") if d.strip()][:4]
    return tags


def send_claim_profile_email(branch, base_url=None):
    """
    Sends the Claim Profile HTML email (matching figma-screens/lab/Claim Profile.png)
    to branch.contact_email and marks branch.claim_email_sent = True on success.
    """
    recipient = (branch.contact_email or "").strip()
    if not recipient:
        return False

    site_url = _get_site_base_url(base_url)
    claim_url = f"{site_url}/register/"
    lab_name = branch.lab_name or "Your Laboratory"
    contact_person = branch.contact_person or lab_name

    context = {
        "lab_name": lab_name,
        "contact_person": contact_person,
        "location": _format_branch_location(branch),
        "categories": _get_branch_category_tags(branch),
        "claim_url": claim_url,
        "public_source": _get_public_source(branch),
        "year": timezone.now().year,
        "site_url": site_url,
    }

    subject = f"{lab_name} is now live on LabFinder360 — Claim Your Profile"
    text_body = (
        f"Hello {contact_person},\n\n"
        f"Congratulations! {lab_name} is now live on LabFinder360.\n"
        f"Claim your official laboratory profile here: {claim_url}\n\n"
        f"— Team LabFinder360"
    )
    html_body = render_to_string("emails/claim_profile.html", context)

    _send_html_email_with_inline_images(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        recipient=recipient,
        inline_images=[
            ("static/images/laboratory_illustration.png", "laboratory_illustration"),
        ],
    )

    branch.claim_email_sent = True
    branch.claim_email_sent_at = timezone.now()
    branch.save(update_fields=["claim_email_sent", "claim_email_sent_at"])
    return True


def send_otp_email(email, otp_code, branch=None, base_url=None):
    """
    Sends the OTP Verification HTML email (matching figma-screens/lab/OTP.png).
    """
    site_url = _get_site_base_url(base_url)
    context = {
        "otp_code": str(otp_code),
        "expiry_minutes": 10,
        "public_source": _get_public_source(branch),
        "year": timezone.now().year,
        "site_url": site_url,
    }

    subject = "Verify your email address — Your LabFinder360 Verification Code"
    text_body = (
        f"Your LabFinder360 verification code is: {otp_code}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you didn't request this code, you can safely ignore this email."
    )
    html_body = render_to_string("emails/otp_verification.html", context)

    _send_html_email_with_inline_images(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        recipient=email,
        inline_images=[
            ("static/images/laboratory_verify_otp.png", "laboratory_verify_otp"),
        ],
    )
    return True


def send_registration_success_email(branch, email=None, base_url=None):
    """
    Sends the Official Verified Lab Badge / Registration Success HTML email
    (matching figma-screens/lab/Badge.png) after OTP verification.
    """
    recipient = (email or (branch.contact_email if branch else "") or "").strip()
    if not recipient:
        return False

    site_url = _get_site_base_url(base_url)
    lab_name = (branch.lab_name if branch else None) or "Your Laboratory"
    contact_person = (branch.contact_person if branch else None) or lab_name
    lab_profile_url = f"{site_url}{branch.get_absolute_url()}" if branch else site_url
    badge_image_url = f"{site_url}/static/images/verified-lab-badge.png"
    dashboard_url = f"{site_url}/dashboard/"
    branch_key = (branch.slug or str(branch.pk)) if branch else ""
    badge_download_url = (
        f"{site_url}{reverse('lab-badge-download', kwargs={'slug': branch_key})}"
        if branch_key
        else badge_image_url
    )
    badge_copy_url = (
        f"{site_url}{reverse('lab-badge-embed', kwargs={'slug': branch_key})}"
        if branch_key
        else dashboard_url
    )

    context = {
        "lab_name": lab_name,
        "contact_person": contact_person,
        "lab_profile_url": lab_profile_url,
        "badge_image_url": badge_image_url,
        "dashboard_url": dashboard_url,
        "badge_download_url": badge_download_url,
        "badge_copy_url": badge_copy_url,
        "public_source": _get_public_source(branch),
        "year": timezone.now().year,
        "site_url": site_url,
    }

    subject = f"Congratulations! {lab_name} is now officially verified on LabFinder360"
    text_body = (
        f"Congratulations {contact_person},\n\n"
        f"{lab_name} is now officially verified on LabFinder360!\n"
        f"Visit your dashboard to get your Verified Laboratory Badge: {dashboard_url}\n"
        f"Your verified profile: {lab_profile_url}\n\n"
        f"— Team LabFinder360"
    )
    html_body = render_to_string("emails/verified_badge.html", context)

    _send_html_email_with_inline_images(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        recipient=recipient,
        inline_images=[
            ("static/images/verified-lab-badge.png", "verified_lab_badge"),
        ],
    )
    return True
