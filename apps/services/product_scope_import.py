from apps.bis.models import Laboratory
from django.db import transaction
from django.db.models import Q
from apps.samples_configurations.models import TestMethod
from apps.services.import_utility import parse_text
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.utility.models import Department
from apps.labs.models import Branch, BranchItem, TestingScopeFacility
from apps.nabl.models import NablLaboratory

import json
from django.forms.models import model_to_dict



def get_or_create_department(name):
    if not name:
        return None
    name = name.strip()[:255]
    if not name:
        return None
    department, _ = Department.objects.get_or_create(name=name)
    return department







########################################
## For NABL Labs ##


# def parse_mf) for v in val.split(",") if v.strip()]


import re


def parse_discipline_and_group(raw_discipline):
    """
    Parses discipline and group from strings formatted like:
      - "BIOLOGICAL- ANIMAL FOOD & FEED"
      - "BIOLOGICAL/ COSMETICS AND ESSENTIAL OILS"
      - "CHEMICAL: POLLUTION & ENVIRONMENT"
      - "BIOLOGICAL"
    """
    if not raw_discipline:
        return "", "GENERAL"

    raw_str = raw_discipline.strip()
    match = re.split(r'[-/:]', raw_str, maxsplit=1)

    if len(match) > 1:
        discipline_str = match[0].strip()
        group_str = match[1].strip() if match[1].strip() else "GENERAL"
    else:
        discipline_str = raw_str
        group_str = "GENERAL"

    return discipline_str, group_str

def get_or_create_clean_department(name):
    """Case-insensitive department lookup."""
    if not name:
        return None
    clean_name = name.strip()[:255]
    dept = Department.objects.filter(name__iexact=clean_name).first()
    if not dept:
        dept = Department.objects.create(name=clean_name)
    return dept





@transaction.atomic
def import_nabl_scope(scope):
    """
    Imports single NABL Scope object mapping:
    - discipline       -> Department & .sub_group
    - productMaterial  -> Product & Category
    - specifictest     -> TestingScopeFacility
    - scopeyear        -> TestMethod .method_test (M2M)
    """
    # ---------------------------------------------------------
    # Step 1. Fetch Laboratory
    # ---------------------------------------------------------
    try:
        nabl_lab = NablLaboratory.objects.using("nabl").get(pk=scope.lab_id_id)
        laboratory_obj = Branch.objects.get(
            source="nabl",
            NABL_code=str(nabl_lab.lab_id_no)
        )
    except (NablLaboratory.DoesNotExist, Branch.DoesNotExist):
        return {"status": "skipped", "reason": "lab_not_found"}

    # ---------------------------------------------------------
    # Step 2. Extract & Parse 4 NABL Fields
    # ---------------------------------------------------------
    try:
        raw_discipline = scope.discipline.strip() if scope.discipline else ""
        raw_product_material = scope.product_material.strip() if scope.product_material else ""
        raw_specific_test = scope.specific_test.strip() if scope.specific_test else ""
        method_name = scope.scope_year.strip() if scope.scope_year else "IN-HOUSE / STANDARD METHOD"

        dept_name, sub_group_name = parse_discipline_and_group(raw_discipline)
    
        # Strictly bound group name and department name to 255 chars
        sub_group_name = sub_group_name[:255] if sub_group_name else "GENERAL"
        department = get_or_create_clean_department(dept_name)

        product_detail = parse_text(raw_product_material)
        
        # Safe Null Handlers for product_detail
        is_number = (product_detail.get('name') or "GENERAL PRODUCT")[:255]
        is_title = product_detail.get('description') or is_number

        # ---------------------------------------------------------
        # Step 4. BranchItem (Lab Scope Mapping)
        # ---------------------------------------------------------
        
        scope_data = json.dumps(model_to_dict(scope), default=str)
        testing_scope, created_scope = BranchItem.objects.get_or_create(
            lab=laboratory_obj,
            is_number=is_number,
            is_title=is_title,
            sub_group=sub_group_name,
            form_type="nabl",
            is_standard=True,
            is_public=True,
            accreditation='nabl',
            defaults={"complete_request": scope_data}
        )
        if not created_scope:
            testing_scope.complete_request = scope_data
            testing_scope.save(update_fields=["complete_request"])

        if department:
            testing_scope.test_type.add(department)

        # ---------------------------------------------------------
        # Step 5. TestMethod (Single string scopeyear)
        # ---------------------------------------------------------
        test_method_obj = None
        if method_name:
            clean_method_name = method_name[:500]
            test_method_obj = TestMethod.objects.filter(lab=laboratory_obj,name__iexact=clean_method_name).first()
            if not test_method_obj:
                test_method_obj = TestMethod.objects.create(
                    lab=laboratory_obj,
                    name=clean_method_name
                )

        # ---------------------------------------------------------
        # Step 6. TestingScopeFacility
        # ---------------------------------------------------------
        created_facilities = []

        parsed_param = parse_text(raw_specific_test)
        
        # Safe Null Handlers for parameter attributes
        raw_clause = parsed_param.get('name') or "General Parameter"
        clause_no = raw_clause[:255]
        title = parsed_param.get('description') or clause_no


        # Create facility entry for parameter
        facility, created_facility = TestingScopeFacility.objects.get_or_create(
            clause_no=clause_no,
            title=title,
            test_type=department,
            lab=laboratory_obj,
            scope=testing_scope,
            defaults={"test_type": department}
        )
        
        needs_update = False
        if department and not facility.test_type:
            facility.test_type = department
            needs_update = True
        
        if not created_facility:
            facility.complete_request = scope_data
            needs_update = True
            
        if needs_update:
            facility.save(update_fields=["test_type", "complete_request"] if not created_facility else ["test_type"])

        if test_method_obj:
            facility.method_test.add(test_method_obj)      

        created_facilities.append(facility)

        return {
            "status": "created" if created_scope else "updated",
            "testing_scope": testing_scope,
            "facility": facility,
            "created_facility": created_facility,
            "laboratory": laboratory_obj,
        }
    except Exception as e:
        return {
                    "status": "skipped",
                    "reason": str(e),
                }
    
    
    ########################################
## For BIS Labs ##


@transaction.atomic
def import_bis_scope(scope):
    # ---------------------------------------------------------
    # Step 1. Fetch Laboratory
    # ---------------------------------------------------------
    try:
        bis_lab = Laboratory.objects.using("bis").get(pk=scope.lab.id)
        BIS_code = None
        if bis_lab.osl_code:
            BIS_code = bis_lab.osl_code
        elif bis_lab.bis_code:
            BIS_code = bis_lab.bis_code
        laboratory_obj = Branch.objects.get(
            source="bis",
            BIS_code=str(BIS_code)
        )
    except (Laboratory.DoesNotExist, Branch.DoesNotExist):
        return {"status": "skipped", "reason": "lab_not_found"}

    # ---------------------------------------------------------
    # 2. Clean source values
    # ---------------------------------------------------------

    try:
        # Use BIS code (or OSL code) as the IS number for the BranchItem
        is_number = scope.is_number
        is_title = is_number.is_title

        if not is_number:
            return {
                "status": "skipped",
                "reason": "missing_master_item_data",
            }

    

        # ---------------------------------------------------------
        # 4. Create/find BranchItem
        # ---------------------------------------------------------

        
        sub_group_name = "GENERAL"
        scope_data = json.dumps(model_to_dict(scope), default=str)

        testing_scope, created_scope = BranchItem.objects.get_or_create(
                    lab=laboratory_obj,
                    is_number=is_number,
                    is_title=is_title,
                    sub_group=sub_group_name,
                    form_type="bis",
                    is_standard=True,
                    is_public=True,
                    accreditation='bis',
                    defaults={"complete_request": scope_data}
                )
        
        if not created_scope:
            testing_scope.complete_request = scope_data
            testing_scope.save(update_fields=["complete_request"])


        # ---------------------------------------------------------
        # Step 6. TestingScopeFacility
        # ---------------------------------------------------------

        scope_facs = scope.facilities.all()
        for scope_fac in scope_facs:
            fac_data = json.dumps(model_to_dict(scope_fac), default=str)
            facility, created_facility = TestingScopeFacility.objects.get_or_create(
                clause_no=scope_fac.clause_no.clause_no,
                lab=laboratory_obj,
                scope=testing_scope,
                defaults={
                    "title":scope_fac.clause_no.title,
                    "complete_request": fac_data
                }
            )

        return {
            "status": "created" if created_scope else "updated",
            "testing_scope": testing_scope,
            "laboratory": laboratory_obj,
        }
    except Exception as e:
        return {
                "status": "skipped",
                "reason": str(e),
            }
