from django.db import transaction
from apps.labs.models import Country, Branch, State, District
from apps.labs.utils.lab_matching import find_existing_lab
import base64
import binascii
import mimetypes
import uuid
from django.core.files.base import ContentFile

# from nabl.models import NablLaboratory
# from bis.models import BISLaboratory


def clean_value(value):
    """
    Convert empty strings to None.
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return value


def parse_date(value):
    """
    NABL/BIS may contain dates in different formats.
    Keep this flexible and return None if the value
    cannot be converted.
    """
    if not value:
        return None

    if hasattr(value, "year"):
        return value

    from datetime import datetime

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d/%b/%Y",
    ]

    value = str(value).strip()

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def convert_bool(value):
    """
    Convert source values such as:
    Yes / No
    Y / N
    True / False
    1 / 0
    into Python boolean values.
    """

    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()

    if value in ("yes", "y", "true", "1"):
        return True

    if value in ("no", "n", "false", "0"):
        return False

    return None




def normalize_text(value):
    """
    Normalize text for comparison.
    """
    if not value:
        return None

    return " ".join(str(value).strip().lower().split())


def get_country(country_value):
    """
    Resolve country name/code/id to Country instance.
    """
    if not country_value:
        return None

    if isinstance(country_value, Country):
        return country_value

    value = normalize_text(country_value)
    if not value:
        return None

    if value.isdigit():
        country = Country.objects.filter(id=int(value)).first()
        if country:
            return country

    value_title = value.title()
    country = Country.objects.filter(name__iexact=value_title).first()
    if not country:
        country, _ = Country.objects.get_or_create(name=value_title)
    return country


def get_state(state_value, country):

    """
    Resolve state name/id to State instance.

    Country is used to avoid matching the same state name
    belonging to another country.
    """

    if not state_value or not country:
        return None

    if isinstance(state_value, State):
        return state_value

    value = normalize_text(state_value)
    if not value:
        return None

    if value.isdigit():
        state = State.objects.filter(id=int(value), country=country).first()
        if not state:
            state = State.objects.filter(id=int(value)).first()
        if state:
            return state

    value_title = value.title()
    state = State.objects.filter(name__iexact=value_title, country=country).first()
    if not state:
        state, _ = State.objects.get_or_create(name=value_title, country=country)
    return state


def get_district(district_value, state):
    """
    Resolve district name/id to District instance.
    """
    if not district_value or not state:
        return None

    if isinstance(district_value, District):
        return district_value

    value = normalize_text(district_value)
    if not value:
        return None

    if value.isdigit():
        district = District.objects.filter(id=int(value), state=state).first()
        if not district:
            district = District.objects.filter(id=int(value)).first()
        if district:
            return district

    value_title = value.title()
    district = District.objects.filter(name__iexact=value_title, state=state).first()
    if not district:
        district, _ = District.objects.get_or_create(name=value_title, state=state)
    return district


# def get_city(city_value, district):
#     """
#     Resolve city.

#     BIS:
#         city + district

#     NABL:
#         city + state
#         because NABL does not provide district.
#     """

#     value = normalize_text(city_value)

#     if not value or not district:
#         return None

#     value = value.capitalize()

#     # # BIS: district is available
#     # if district:
#     #     city, created = City.objects.get_or_create(
#     #         name=value,
#     #         district=district
#     #     )
#     #     return city

#     # # NABL: district is not available
#     # else:
#     #     city = City.objects.filter(
#     #         name=value,
#     #         district__state=state
#     #     ).first()
#     #     if city:
#     #         return city

#     #     district, created = District.objects.get_or_create(
#     #         name=value,
#     #         state=state
#     #     )
#     #     city, created = City.objects.get_or_create(
#     #         name=value,
#     #         district=district
#     #     )
#     city, created = City.objects.get_or_create(
#         name=value,
#         district=district
#     )

#     return city


import base64
import binascii
import mimetypes
import uuid

import requests

from django.core.files.base import ContentFile


def save_image(branch, image, field_name):
    """
    Save an image to a specified model ImageField/FileField.

    Priority:
    1. Base64
    2. URL

    Example:
        save_image(branch, image_data, "lab_logo")
        save_image(branch, image_data, "nabl_logo")
        save_image(branch, image_data, "cover_picture")
    """
    if not isinstance(image, dict):
        return False

    base64_data = image.get("base64")
    logo_url = image.get("url")

    # ---------------------------------------------------------
    # 1. Try BASE64
    # ---------------------------------------------------------
    if base64_data:
        try:
            if "," in base64_data:
                header, encoded_data = base64_data.split(",", 1)
            else:
                header = ""
                encoded_data = base64_data

            file_data = base64.b64decode(
                encoded_data,
                validate=True
            )

            # Determine extension
            extension = ".png"

            if header.startswith("data:"):
                mime_type = header.split(";", 1)[0].replace(
                    "data:",
                    ""
                )

                extension = (
                    mimetypes.guess_extension(mime_type)
                    or ".png"
                )

            filename = "image_{}{}".format(
                uuid.uuid4().hex,
                extension
            )

            getattr(branch, field_name).save(
                filename,
                ContentFile(file_data),
                save=False
            )

            return True

        except (
            ValueError,
            binascii.Error,
            TypeError
        ):
            pass

    # ---------------------------------------------------------
    # 2. Fallback to URL
    # ---------------------------------------------------------
    if logo_url:
        try:
            response = requests.get(
                logo_url,
                timeout=15
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type",
                "image/png"
            ).split(";")[0]

            extension = (
                mimetypes.guess_extension(content_type)
                or ".png"
            )

            filename = "image_{}{}".format(
                uuid.uuid4().hex,
                extension
            )

            getattr(branch, field_name).save(
                filename,
                ContentFile(response.content),
                save=False
            )

            return True

        except Exception:
            pass

    return False

########################################
## For NABL Labs ##
def import_nabl_laboratory(nabl_lab):
    """
    Create/update LabFinder Branch from NablLaboratory.

    Matching priority:

    1. Same laboratory name + city + state using fuzzy matching
    2. Create new Branch
    """
    NABL_code = clean_value(nabl_lab.lab_id_no)


    country = Country.objects.get(name="India")
    state = get_state(nabl_lab.state,country)
    city = normalize_text(nabl_lab.city)
    if city:
        city = city.capitalize() 

    region_code = clean_value(nabl_lab.zone)
    region = ""
    if region_code:
        if region_code == "Eastern":
            region = "eastern"
        elif region_code == "Southern":
            region = "southern"
        elif region_code == "Western":
            region = "western"
        elif region_code == "Central":
            region = "central"
        elif region_code == "North":
            region = "northern"

    lab_name = clean_value(nabl_lab.lab_name)
    defaults = {
        "source": "nabl",
        "NABL_code": NABL_code,
        "lab_code": NABL_code,
        "lab_name": lab_name,
        "lab_type": clean_value(nabl_lab.lab_type),
        "standard": clean_value(nabl_lab.standard),
        "assessment_types": clean_value(nabl_lab.assessment_types),

        "contact_person": clean_value(nabl_lab.contact_person),
        "contact_email": clean_value(nabl_lab.contact_email),
        "contact_mobile": clean_value(nabl_lab.contact_mobile),
        "land_line": clean_value(nabl_lab.land_line),
        "fax": clean_value(nabl_lab.fax),

        "lab_address": clean_value(nabl_lab.prime_address),

        "lab_city": city,
        "lab_district": None,
        "lab_state": state,
        "lab_country": country,

        "lab_pincode": clean_value(nabl_lab.pin),
        "lab_region": region,
        "description": clean_value(nabl_lab.description),
        "li_type_of_lab_by_service": clean_value(
            nabl_lab.li_type_of_lab_by_service
        ),

        "cert_no": clean_value(nabl_lab.cert_no),

        "issue_date": parse_date(nabl_lab.issue_date),
        "extend_date": parse_date(nabl_lab.extend_date),
        "to_date": parse_date(nabl_lab.to_date),
        "amendment_date": parse_date(nabl_lab.amendment_date),

        "certificate_url": clean_value(nabl_lab.certificate_url),

        "discipline_name": clean_value(nabl_lab.discipline_name),
        "group_name": clean_value(nabl_lab.group_name),
        "sub_group_name": clean_value(nabl_lab.sub_grp_name),

        "permanent_facility": convert_bool(
            nabl_lab.permanent_facility
        ),
        "site_facility": convert_bool(
            nabl_lab.site_facility
        ),
        "mobile_facility": convert_bool(
            nabl_lab.mobile_facility
        ),
        "is_active": True,
    }

    # ============================================================
    # STEP 1
    # Check exact NABL source record
    # ============================================================

    laboratory = Branch.objects.filter(
        source="nabl",
        NABL_code=NABL_code,
    ).first()

    if laboratory:
        # Existing exact NABL record.
        # Update it.
        for field, value in defaults.items():
            current_val = getattr(laboratory, field, None)
            if current_val in [None, ""] or (isinstance(current_val, str) and not current_val.strip()):
                setattr(laboratory, field, value)
        laboratory.save()
        return laboratory, False

    # ============================================================
    # STEP 2
    # Check fuzzy duplicate
    #
    # Same:
    #     State
    #     City
    #
    # Similar:
    #     Laboratory name
    # ============================================================

    existing_lab = find_existing_lab(
        name=lab_name,
        city=city,
        state=state,
        threshold=90,
    )

    if existing_lab:        
        for field, value in defaults.items():
            current_val = getattr(existing_lab, field, None)
            if current_val in [None, ""] or (isinstance(current_val, str) and not current_val.strip()):
                setattr(existing_lab, field, value)
        existing_lab.save()
        return existing_lab, False

    laboratory = Branch.objects.create(
        **defaults
    )

    return laboratory, True


## For BIS Labs ## 
def import_bis_laboratory(bis_lab):
    """
    Create/update LabFinder Branch from BISLaboratory.
    """

    country = Country.objects.get(name="India")   
    state = get_state(bis_lab.lab_state,country)         
    district = get_district(bis_lab.lab_district,state) 
    city = normalize_text(bis_lab.lab_city)
    if city:
        city = city.capitalize()    

    registered_office_state = get_state(bis_lab.registered_office_state, country) 
    registered_office_district = get_district(bis_lab.registered_office_district, registered_office_state) 
    registered_office_city = normalize_text(bis_lab.registered_office_city)
    if registered_office_city:
        registered_office_city = registered_office_city.title()
    if bis_lab.bis_code:
        lab_code = bis_lab.bis_code
    elif bis_lab.osl_code:
        lab_code = bis_lab.osl_code 
    else:
        lab_code = bis_lab.lab_id_no

    region_code = clean_value(bis_lab.region)
    region = ""
    if region_code:
        if region_code == "51":
            region = "eastern"
        elif region_code == "61":
            region = "southern"
        elif region_code == "71":
            region = "western"
        elif region_code == "81":
            region = "central"
        elif region_code == "91":
            region = "northern"

    lab_name = clean_value(bis_lab.lab_name)
    defaults = {
        "source": "bis",
        "lab_name": lab_name,
        "lab_code": lab_code,
        "BIS_code": lab_code,
        "lab_type": clean_value(bis_lab.lab_type),
        "discipline": clean_value(bis_lab.discipline),
        "lab_region": region,
        "lab_address": clean_value(bis_lab.lab_address),
        "lab_city": city,
        "lab_district": district,
        "lab_state": state,
        "lab_country": country,
        "lab_pincode": clean_value(bis_lab.lab_zipcode),
        "registered_office_same_as_lab":bis_lab.registered_office_same_as_lab,
        "registered_office_address":clean_value(bis_lab.registered_office_address),
        "registered_office_city":registered_office_city,
        "registered_office_district":registered_office_district,
        "registered_office_state":registered_office_state,
        "registered_office_country":country,
        "registered_office_pincode":
            clean_value(bis_lab.registered_office_zipcode),
        "registered_office_mobile":
            clean_value(bis_lab.registered_office_mobile1),
        "registered_office_telephone":
            clean_value(bis_lab.registered_office_telephone),
        "registered_office_fax":
            clean_value(bis_lab.registered_office_fax),
        "website_url": clean_value(
            getattr(bis_lab, "website_url", None)
        ),

        "is_active": True,
        # "raw_data":bis_lab
    }


    # return laboratory, created

    laboratory = Branch.objects.filter(
            source="bis",
            BIS_code=lab_code,
    ).first()
    
    if laboratory:
        # Existing exact BIS record.
        # Update it.
        for field, value in defaults.items():
            current_val = getattr(laboratory, field, None)
            if current_val in [None, ""] or (isinstance(current_val, str) and not current_val.strip()):
                setattr(laboratory, field, value)

        image_fields = {
            "lab_logo": bis_lab.lab_logo,
            "nabl_logo": bis_lab.nabl_logo,
            "cover_picture": bis_lab.cover_picture,
        }

        for field_name, image in image_fields.items():
            current_image = getattr(laboratory, field_name, None)
            if not current_image:
                save_image(
                    laboratory,
                    image,
                    field_name
                )
        laboratory.save()
        return laboratory, False

        
    
    existing_lab = find_existing_lab(
        name=lab_name,
        city=city,
        state=state,
        threshold=90,
    )
    
    if existing_lab:
        if not existing_lab.lab_code:
            existing_lab.lab_code = lab_code               
        for field, value in defaults.items():
            current_val = getattr(existing_lab, field, None)
            if current_val in [None, ""] or (isinstance(current_val, str) and not current_val.strip()):
                setattr(existing_lab, field, value)
        existing_lab.save()    
        return existing_lab, False
    
    laboratory = Branch.objects.create(
        **defaults
    )

    return laboratory, True
    