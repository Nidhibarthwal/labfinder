"""
vista_sync.py
=============
Fetches branch data from the Vista backend API and saves it into the
LabFinder models:

  Vista JSON                        →  LabFinder model
  ─────────────────────────────────────────────────────
  root object                       →  Branch
  accreditations[].accred           →  AccreditationMaster (get_or_create)
  accreditations[]                  →  Accreditation
  manpowers[]                       →  BranchManpower  (user created on-fly)
  manpowers[].roles[]               →  ManpowerRoleDepartment + ManpowerRoles
  manpowers[].roles[].departments_list → Department (get_or_create)
  scopes[]                          →  BranchItem
  scopes[].facilities[]             →  TestingScopeFacility
"""

from apps.utility.models import Country
from apps.utility.models import State
from apps.utility.models import District
import logging
from django.contrib.auth import get_user_model
from django.db import transaction

import requests

from apps.labs.models import (
    Accreditation,
    BranchItem,
    BranchManpower,
    Discipline,
    ManpowerRoleDepartment,
    ManpowerRoles,
    TestingScopeFacility,
    Branch,
)
from apps.services.import_utility import save_image_db_field
from apps.utility.models import AccreditationMaster, Department, Role

logger = logging.getLogger(__name__)
User = get_user_model()

VISTA_BRANCH_DETAILS_URL = "https://vistabackend.stagemyapp.com/labs/branch-details/"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def fetch_vista_branch_details(timeout: int = 60) -> list:
    """
    Fetch the full branch-details list from the Vista backend.
    Returns a list of branch dicts.
    Raises requests.HTTPError on non-2xx responses.
    """
    response = requests.get(VISTA_BRANCH_DETAILS_URL, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return data
    # Some APIs wrap in a key
    if isinstance(data, dict):
        for key in ("results", "data", "branches", "labs"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_location(country_name=None, state_name=None, district_name=None):
    """
    Create or retrieve Country, State, and District records locally.
    Missing district does not prevent saving country or state.
    """
    country = None
    state = None
    district = None

    country_name = (country_name or "").strip()
    state_name = (state_name or "").strip()
    district_name = (district_name or "").strip()

    if country_name:
        country, _ = Country.objects.get_or_create(
            name=country_name
        )

    if country and state_name:
        state, _ = State.objects.get_or_create(
            name=state_name,
            country=country,
        )

    if state and district_name:
        district, _ = District.objects.get_or_create(
            name=district_name,
            state=state,
        )

    return country, state, district

def _sync_branch(item: dict) -> tuple:
    """
    Create or update a Branch from a Vista branch dict.
    Returns (branch, created).
    """
    # vista_id = item.get("id") or ""
    lab_id_no = item.get("lab_id_no") or ""
    lab_code = item.get("lab_code") or ""

    # Try to match on Vista-specific fields first
    branch = (
        Branch.objects.filter(VISTA_code=lab_code).first()
        or (Branch.objects.filter(VISTA_code=lab_id_no).first() if lab_id_no else None)
    )
    created = False
    
    lab_country, lab_state, lab_district = _get_location(
        country_name=item.get("lab_country_name"),
        state_name=item.get("lab_state_name"),
        district_name=item.get("lab_district"),
    )

    reg_off_country, reg_off_state, reg_off_district = _get_location(
        country_name=item.get("reg_off_country_name"),
        state_name=item.get("reg_off_state_name"),
        district_name=item.get("reg_off_district"),
    )

    org_country, org_state, org_district = _get_location(
        country_name=item.get("org_country_name"),
        state_name=item.get("org_state_name"),
        district_name=item.get("org_district"),
    )
    
    region_code = item.get("region")
    region = ""
    if region_code:
        if region_code == "51":
            region = "eastern"
        elif region_code == "61":
            region = "southern"
        elif region_code == "71":
            region = "western"
        elif region_code == "Central":
            region = "central"
        elif region_code == "91":
            region = "northern"
        elif region_code == "92":
            region = "NER"
        elif region_code == "93":
            region = "NWR"
        elif region_code == "94":
            region = "NC"
        elif region_code == "81":
            region = "HQ"

    defaults = {
        "lab_name": item.get("lab_name") or "",
        "lab_name_hindi": item.get("lab_name_hindi") or "",
        "lab_address": item.get("lab_address") or "",
        "lab_city": item.get("lab_city") or "",
        "lab_district":lab_district,
        "lab_state": lab_state,
        "lab_country": lab_country,
        "lab_pincode": item.get("lab_zipcode") or "",
        "lab_region": region,
        "registered_office_same_as_lab": bool(item.get("reg_off_same_as_lab")) if item.get("reg_off_same_as_lab") else False,
        "registered_office_address": item.get("reg_off_address") or "",
        "registered_office_city": item.get("reg_off_city") or "",
        "registered_office_district": reg_off_district,
        "registered_office_state": reg_off_state,
        "registered_office_country": reg_off_country,
        "registered_office_pincode": item.get("reg_off_zipcode") or "",
        "registered_office_mobile": item.get("reg_off_mobile1") or "",
        "registered_office_telephone": item.get("reg_off_tel") or "",
        "registered_office_fax": item.get("reg_off_fax") or "",
        "org_name": item.get("org_name") or "",
        "org_address": item.get("org_address") or "",
        "org_city": item.get("org_city") or "",
        "org_district": org_district,
        "org_state": org_state,
        "org_country": org_country,
        "org_zipcode": item.get("org_zipcode") or "",
        "org_doc_other": item.get("org_doc_other") or "",
        "org_office_same_as_lab": bool(item.get("org_office_same_as_lab"))if item.get("org_office_same_as_lab") else False,        
        "website_url": item.get("website_url") or None,
        "contact_email": item.get("lab_email") or None,
        "lab_code": item.get("lab_code") or None,
        "logo_base64": item.get("logo_base64") or None,
        "logo_footer_base64": item.get("logo_footer_base64") or None,
        "cover_base64": item.get("cover_base64") or None,
        "address_in_hi":item.get("address_in_hi") or None,
        "source": "vista",  # Vista is "other" in SOURCE_CHOICES
    }

    if branch is None:
        branch = Branch(
            VISTA_code=lab_id_no or lab_code,
            **defaults,
        )
        branch.save()
        created = True
    else:
        for field, value in defaults.items():
            setattr(branch, field, value)
        branch.save(update_fields=list(defaults.keys()))

    user, u_created = User.objects.get_or_create(username=item.get("lab_email"))
    branch.user = user

    discipline = item.get("discipline")
    if discipline:
        discipline, dcreate = Discipline.objects.get_or_create(name=discipline)
        branch.disciplines.add(discipline)
    branch.save()

    image_fields = {
        "lab_logo": item.get("lab_logo") or None,
        "lab_footer_logo": item.get("lab_footer_logo") or None,
        "nabl_logo": item.get("nabl_logo") or None,
        "cover_picture": item.get("cover_picture") or None,
        "nabl_logo_calibration": item.get("nabl_logo_calibration") or None,
    }
    for field_name, image in image_fields.items():
        save_image_db_field(
            branch,
            image,
            field_name
        )
    branch.save()

    return branch, created


def _sync_accreditations(branch: Branch, accreditations: list) -> dict:
    """
    Sync accreditations for a branch.
    Returns a dict mapping Vista accreditation UUID → Accreditation instance.
    """
    acc_map: dict = {}
    for acc_data in accreditations:
        acc_id = acc_data.get("id")
        accred_master_info = acc_data.get("accred") or {}
        accred_name = accred_master_info.get("name") or "Unknown"

        # Get or create the master record
        master, _ = AccreditationMaster.objects.get_or_create(
            name=accred_name,
            defaults={
                "vista_id":accred_master_info.get("id"),
                "active": True
                },
        )

        # Upsert the Accreditation record keyed by (lab, certificate_no)
        cert_no = acc_data.get("certificate_no") or acc_id or ""
        acc_obj, _ = Accreditation.objects.update_or_create(
            lab=branch,
            certificate_no=cert_no,
            defaults={
                "accred": master,
                "name": accred_name,
                "logo_base64":acc_data.get("logo_base64") or None,
                "certificate_img_base64":acc_data.get("certificate_img_base64") or None,
                "validity_from": acc_data.get("validity_from") or None,
                "validity_to": acc_data.get("validity_to") or None,
                "renewal_date": acc_data.get("renewal_date") or None,
                "active": bool(acc_data.get("active", True)),
            },
        )

        image_fields = {
            "logo": acc_data.get("logo"),
            "certificate_img":acc_data.get("certificate_img")
        }
        for field_name, image in image_fields.items():
            save_image_db_field(
                acc_obj,
                image,
                field_name
            )
        acc_obj.save()
                
        if acc_id:
            acc_map[acc_id] = acc_obj

    return acc_map


def _get_or_create_department(dept_data: dict) -> Department:
    """Return a Department, creating it if needed (case-insensitive name match)."""
    name = (dept_data.get("name") or "").strip()
    if not name:
        return None
    dept = Department.objects.filter(name__iexact=name).first()
    if dept is None:
        dept = Department(name=name)
        dept.save()
    return dept


def _get_or_create_role(role_name: str = "Manpower") -> Role:
    """Return a Role master record."""
    role, _ = Role.objects.get_or_create(
        name=role_name,
        defaults={"code": role_name[:30]},
    )
    return role


def _get_or_create_user(email: str, first_name: str = "", last_name: str = "") -> User:
    """Return a User for the given email, creating a placeholder if absent."""
    email = (email or "").strip().lower()
    if not email:
        return None
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": first_name[:150],
            "last_name": last_name[:150],
        },
    )
    return user


def _sync_manpowers(branch: Branch, manpowers: list) -> None:
    """
    Sync manpowers for a branch.

    Vista structure:
      manpower → BranchManpower  (one per person / email)
      manpower.roles[] → ManpowerRoleDepartment  (role+depts combination)
      ManpowerRoles through-table links BranchManpower ↔ ManpowerRoleDepartment
    """
    EMPLOYMENT_MAP = {
        "1": "permanent",
        "2": "contract",
        "3": "permanent",
    }

    default_role = _get_or_create_role("Manpower")

    for mp_data in manpowers:
        email = (mp_data.get("email") or "").strip()
        first_name = (mp_data.get("first_name") or "").strip()
        last_name = (mp_data.get("last_name") or "").strip()

        user = _get_or_create_user(email, first_name, last_name)
        if user is None:
            logger.warning("Skipping manpower with no email: %s", mp_data.get("id"))
            continue

        emp_status_raw = str(mp_data.get("emp_status") or "")
        emp_status = EMPLOYMENT_MAP.get(emp_status_raw) or None

        manpower_obj, _ = BranchManpower.objects.update_or_create(
            user=user,
            defaults={
                "lab": branch,
                "designation": (mp_data.get("designation") or "")[:35],
                "emp_status": emp_status,
                "type": mp_data.get("type"),
            },
        )

        # ── Roles ──────────────────────────────────────────────────────────
        # Each role entry in Vista represents a ManpowerRoleDepartment
        for role_data in mp_data.get("roles") or []:
            dept_objs = []
            for dept_data in role_data.get("departments_list") or []:
                dept = _get_or_create_department(dept_data)
                if dept:
                    dept_objs.append(dept)

            validity = role_data.get("validity")

            # Create/update a ManpowerRoleDepartment scoped to this lab
            mrd, _ = ManpowerRoleDepartment.objects.get_or_create(
                lab=branch,
                group=default_role,
                validity=validity,
                defaults={},
            )
            if dept_objs:
                mrd.departments.set(dept_objs)

            # Through-table: link manpower ↔ mrd
            ManpowerRoles.objects.get_or_create(
                manpower=manpower_obj,
                role=mrd,
                defaults={"default_role": False, "order": 1},
            )


def _sync_scopes(branch: Branch, scopes: list) -> None:
    """
    Sync scopes and their facilities for a branch.

    Vista structure:
      scope → BranchItem  (keyed on standard_id)
      scope.facilities[] → TestingScopeFacility  (keyed on parameter_id)
    """
    for scope_data in scopes:
        standard_id = scope_data.get("standard_id") or ""
        standard_name = scope_data.get("standard_name") or ""
        complete_test_charges_raw = scope_data.get("complete_test_charges")

        try:
            complete_test_charges = (
                float(complete_test_charges_raw)
                if complete_test_charges_raw not in (None, "", "null")
                else None
            )
        except (ValueError, TypeError):
            complete_test_charges = None

        # BranchItem keyed on (lab, standard_id)
        scope_obj, _ = BranchItem.objects.update_or_create(
            lab=branch,
            standard_id=standard_id,
            defaults={
                "is_number": standard_name[:550] if standard_name else standard_id[:550],
                "is_title": standard_name,
                "is_disable": bool(scope_data.get("disable", False)),
                "remarks": scope_data.get("remarks") or None,
                "complete_test_charges": complete_test_charges,
                "source": "other",
                "form_type": "lims",
            },
        )

        # ── Facilities ────────────────────────────────────────────────────
        for fac_data in scope_data.get("facilities") or []:
            parameter_id = fac_data.get("parameter_id") or ""
            parameter_name = fac_data.get("parameter_name") or ""
            quantity = fac_data.get("quantity") or 1
            charges = fac_data.get("charges") or 0

            TestingScopeFacility.objects.update_or_create(
                scope=scope_obj,
                parameter_id=parameter_id,
                defaults={
                    "lab": branch,
                    "clause_no": parameter_id,
                    "parameter": parameter_name,
                    "title": parameter_name,
                    "quantity": quantity,
                    "charges": float(charges),
                },
            )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@transaction.atomic
def sync_single_branch(item: dict) -> dict:
    """
    Fully sync one Vista branch dict into the local database.
    Returns a summary dict.
    """
    branch, created = _sync_branch(item)

    _sync_accreditations(branch, item.get("accreditations") or [])
    _sync_manpowers(branch, item.get("manpowers") or [])
    _sync_scopes(branch, item.get("scopes") or [])

    return {
        "branch_id": str(branch.id),
        "lab_name": branch.lab_name,
        "created": created,
        "accreditations": len(item.get("accreditations") or []),
        "manpowers": len(item.get("manpowers") or []),
        "scopes": len(item.get("scopes") or []),
    }


def sync_all_branches(data: list) -> dict:
    """
    Iterate over all branches returned by Vista and sync them one-by-one.
    Errors on individual branches are caught and logged so the rest continue.
    Returns an aggregate summary dict.
    """
    summary = {
        "total": len(data),
        "created": 0,
        "updated": 0,
        "failed": 0,
        "branches": [],
    }

    for item in data:
        try:
            result = sync_single_branch(item)
            if result["created"]:
                summary["created"] += 1
            else:
                summary["updated"] += 1
            summary["branches"].append(result)
        except Exception as exc:
            summary["failed"] += 1
            logger.exception(
                "Failed to sync Vista branch %s: %s",
                item.get("lab_id_no") or item.get("id"),
                exc,
            )
            print("+++++++++++ Exception -----------",exc)

    return summary


