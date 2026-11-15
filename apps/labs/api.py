from apps.services.product_scope_import import import_bis_scope
from apps.bis.models import LaboratoryScopes
from django.db import transaction
from django.db.models import Q
from apps.services.product_scope_import import import_nabl_scope
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.labs.vista_sync import fetch_vista_branch_details, sync_all_branches
from apps.bis.models import Laboratory as BisLaboratory
from django.template.loader import render_to_string


from apps.nabl.models import NablLaboratory, NablLaboratoryScopes
from apps.services.laboratory_import import import_bis_laboratory, import_nabl_laboratory
from django.shortcuts import get_object_or_404
from django.utils.text import slugify

from .models import Branch, BranchItem, Accreditation, LabSocialLink, LabWebPage, ProductService
from apps.utility.models import AccreditationMaster
from .serializers import BranchSerializer, LabCrawlerImportSerializer
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import JsonResponse


import base64
import binascii
import mimetypes
import os
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


# from nabl.models import NablLaboratory


class LaboratoryImportAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    '''
    {
        "source": "all"
        or
        "source": "BIS"
        or 
        "source": "NABL"
    }
    '''

    def post(self, request):

        source = request.data.get("source")

        if source not in ("all", "nabl", "bis"):
            return Response(
                {
                    "success": False,
                    "message": "Invalid source. Use all, nabl or bis."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        result = {
            "nabl": {
                "total": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
            },
            "bis": {
                "total": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
            }
        }

        # --------------------------------------------------------
        # NABL
        # --------------------------------------------------------

        if source == "nabl":
            # nabl_labs = NablLaboratory.objects.all()
            nabl_labs = NablLaboratory.objects.using("nabl").all()
            result["nabl"]["total"] = nabl_labs.count()
            for nabl_lab in nabl_labs:
                laboratory, created = import_nabl_laboratory(
                    nabl_lab
                )
                if laboratory is None:
                    result["nabl"]["skipped"] += 1
                elif created:
                    result["nabl"]["created"] += 1
                else:
                    result["nabl"]["updated"] += 1

        elif source == "bis":
            # --------------------------------------------------------
            # BIS
            # --------------------------------------------------------
            from apps.bis.models import Laboratory
            bis_labs = Laboratory.objects.filter(state=7).using("bis")
            result["bis"]["total"] = bis_labs.count()
            for bis_lab in bis_labs:
                laboratory, created = import_bis_laboratory(
                    bis_lab
                )
                if laboratory is None:
                    result["bis"]["skipped"] += 1
                elif created:
                    result["bis"]["created"] += 1
                else:
                    result["bis"]["updated"] += 1

        return Response(
            {
                "success": True,
                "message": "Laboratory import completed successfully.",
                "result": result,
            },
            status=status.HTTP_200_OK
        )



class ImportScopeAPIView(APIView):
    """
    python manage.py run_scope_import --source=nabl --batch-size=500         
    POST /import/scope/
    Payload / Query Params:
    {
        "source": "all" | "nabl" | "bis",
        "offset": 0,
        "limit": 500
    }
    """

    def post(self, request):
        source = request.data.get("source", "").strip().lower()
        if source not in ("all", "nabl", "bis"):
            return Response(
                {
                    "success": False,
                    "message": "Invalid source. Use 'all', 'nabl', or 'bis'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse offset and limit
        try:
            offset = max(0, int(request.data.get("offset", request.query_params.get("offset", 0))))
            limit = int(request.data.get("limit", request.query_params.get("limit", 500)))
            limit = min(limit, 2000)  # Max cap per batch to prevent memory spikes
        except (ValueError, TypeError):
            return Response(
                {
                    "success": False,
                    "message": "Invalid offset or limit parameters. Must be integers.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            "success": True,
            "batch_info": {
                "offset": offset,
                "limit": limit,
            }
        }

        # ------------------------------------------------------------------
        # NABL Import
        # ------------------------------------------------------------------
        if source in ("all", "nabl"):
            nabl_qs = NablLaboratoryScopes.objects.using("nabl").all().order_by("id")
            total_nabl = nabl_qs.count()

            # Slice queryset using offset and limit
            nabl_scopes = nabl_qs[offset: offset + limit]

            nabl_result = {
                "total_records_in_db": total_nabl,
                "processed_in_batch": len(nabl_scopes),
                "has_more": (offset + limit) < total_nabl,
                "next_offset": offset + limit if (offset + limit) < total_nabl else None,
                "testing_scope_created": 0,
                "testing_scope_updated": 0,
                "skipped": 0,
                "nabl_lab_not_found": 0,
                "labfinder_lab_not_found": 0,
                "missing_master_item_data": 0,
            }

            for scope in nabl_scopes:
                try:
                    with transaction.atomic():
                        data = import_nabl_scope(scope)

                    if data["status"] == "skipped":
                        nabl_result["skipped"] += 1
                        if data.get("reason") in nabl_result:
                            nabl_result[data["reason"]] += 1
                        continue

                    if data["status"] == "created":
                        nabl_result["testing_scope_created"] += 1
                    else:
                        nabl_result["testing_scope_updated"] += 1

                

                except Exception as exc:
                    nabl_result["skipped"] += 1
                    print(f"NABL scope import failed for scope ID {scope.id}: {exc}")

            response_data["nabl_result"] = nabl_result
            response_data["nabl_message"] = f"Processed batch {offset} to {offset + len(nabl_scopes)} of {total_nabl} NABL scopes."

        # ------------------------------------------------------------------
        # BIS Import
        # ------------------------------------------------------------------
        if source == 'bis':
            bis_qs = LaboratoryScopes.objects.using("bis").all().order_by("id")
            total_bis = bis_qs.count()

            # Slice queryset using offset and limit
            bis_scopes = bis_qs[offset: offset + limit]

            bis_result = {
                "total_records_in_db": total_bis,
                "processed_in_batch": len(bis_scopes),
                "has_more": (offset + limit) < total_bis,
                "next_offset": offset + limit if (offset + limit) < total_bis else None,
                "testing_scope_created": 0,
                "testing_scope_updated": 0,
                "skipped": 0,
                "bis_lab_not_found": 0,
                "labfinder_lab_not_found": 0,
                "missing_master_item_data": 0,
            }

            for scope in bis_scopes:
                try:
                    with transaction.atomic():
                        data = import_bis_scope(scope)
                    if data["status"] == "skipped":
                        bis_result["skipped"] += 1
                        if data.get("reason") in bis_result:
                            bis_result[data["reason"]] += 1
                        continue

                    if data["status"] == "created":
                        bis_result["testing_scope_created"] += 1
                    else:
                        bis_result["testing_scope_updated"] += 1

                   

                except Exception as exc:
                    bis_result["skipped"] += 1
                    print(f"BIS scope import failed for BIS lab ID {bis_lab.id}: {exc}")

            response_data["bis_result"] = bis_result
            response_data["bis_message"] = f"Processed batch {offset} to {offset + len(bis_labs)} of {total_bis} BIS scopes."

        return Response(response_data, status=status.HTTP_200_OK)




class LabCrawlerDataIngestAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    # def initialize_request(self, request, *args, **kwargs):
    #     req = super().initialize_request(request, *args, **kwargs)
    #     req._dont_enforce_csrf_checks = True
    #     return req

    def _save_crawler_logo(self, branch, logo_data):
        """
        Save crawler logo into Branch.lab_logo.

        Priority:
        1. base64
        2. URL
        """

        if not isinstance(logo_data, dict):
            return

        base64_data = logo_data.get("base64")
        logo_url = logo_data.get("url")
        # ---------------------------------------------------------
        # 1. Try BASE64
        # ---------------------------------------------------------
        if base64_data:
            try:
                # Example:
                # data:image/png;base64,iVBORw0KGgoAAA...
                if "," in base64_data:
                    header, encoded_data = base64_data.split(",", 1)
                else:
                    header = ""
                    encoded_data = base64_data
                file_data = base64.b64decode(encoded_data)
                # Determine extension from data:image/png;base64
                extension = ".png"
                if header.startswith("data:"):
                    mime_type = header.split(";", 1)[0].replace("data:", "")
                    extension = mimetypes.guess_extension(mime_type) or ".png"
                filename = "logo_{}{}".format(
                    uuid.uuid4().hex,
                    extension
                )
                branch.lab_logo.save(
                    filename,
                    ContentFile(file_data),
                    save=False
                )
                return True
            except (ValueError, binascii.Error, TypeError):
                pass

        # ---------------------------------------------------------
        # 2. Fallback to URL
        # ---------------------------------------------------------
        if logo_url:
            try:
                import requests
                response = requests.get(
                    logo_url,
                    timeout=15
                )
                response.raise_for_status()
                content_type = response.headers.get(
                    "Content-Type",
                    "image/png"
                ).split(";")[0]
                extension = mimetypes.guess_extension(content_type) or ".png"
                filename = "logo_{}{}".format(
                    uuid.uuid4().hex,
                    extension
                )
                branch.lab_logo.save(
                    filename,
                    ContentFile(response.content),
                    save=False
                )
                return True
            except Exception:
                pass

        return False

    def _save_page_tree(self, branch, pages_data, parent_page=None):
        """Recursively parses and creates menu-submenu hierarchies in LabWebPage."""
        for order, page_info in enumerate(pages_data):
            page_type = page_info.get('page_type', 'OTHER').upper()
            title = page_info.get('title', 'Untitled')
            url = page_info.get('url', '')

            if not url:
                continue

            valid_page_type = page_type if page_type in dict(LabWebPage.PAGE_TYPE_CHOICES) else 'OTHER'

            page_obj, _ = LabWebPage.objects.update_or_create(
                lab=branch,
                url=url,
                defaults={
                    'parent': parent_page,
                    'title': title,
                    'slug': slugify(title)[:255],
                    'page_type': valid_page_type,
                    'normalized_url': page_info.get('normalized_url'),
                    'quality_score': page_info.get('quality_score', 0.0),
                    'fetch_method': page_info.get('fetch_method', 'HTTP'),
                    'menu_order': order,
                    'is_active': True,
                }
            )

            # Process nested submenus recursively
            nested_pages = page_info.get('pages', [])
            if isinstance(nested_pages, list) and nested_pages:
                self._save_page_tree(branch, nested_pages, parent_page=page_obj)

    def _save_social_links(self, branch, social_links):                
        for platform, social_url in social_links.items():
            if not social_url:
                continue
            platform = platform.lower().strip()
            social_url = social_url.strip()
            # Only save supported platforms
            valid_platforms = dict(LabSocialLink.PLATFORM_CHOICES)
            if platform not in valid_platforms:
                platform = "other"
            LabSocialLink.objects.update_or_create(
                lab=branch,
                platform=platform,
                defaults={
                    "url": social_url,
                    "is_active": True,
                }
            )

    def _save_accreditations(self, branch, accreditations):
        for acc_data in accreditations:
            acc_name = acc_data.get('name')
            acc_full_name = acc_data.get('full_name')
            acc_type_str = acc_data.get('accreditation_type', 'General')
            if not acc_name:
                continue
            # Create or resolve master type record
            master_obj, _ = AccreditationMaster.objects.get_or_create(
                name=acc_type_str
            )
            # Mappings: name -> name & certificate_no, full_name -> full_name
            status_value = str(acc_data.get("status", "")).strip().lower()
            active = status_value in ("active", "approved", "valid")
            Accreditation.objects.update_or_create(
                lab=branch,
                name=acc_name,
                defaults={
                    'accred': master_obj,
                    'certificate_no': acc_name,
                    'full_name': acc_full_name,
                    'active': active,
                    'validity_from': acc_data.get('valid_from'),
                    'validity_to':acc_data.get('valid_until')
                }
            )
               
    # def _save_product_services(self, branch, products_services):
    #     for item in products_services:
    #         item_name = item.get('name')
    #         item_summary = item.get('summary', '')
    #         if not item_name:
    #             continue
    #         # Mappings: name -> is_number, summary -> is_title
    #         BranchItem.objects.update_or_create(
    #             lab=branch,
    #             is_number=item_name,
    #             defaults={
    #                 'is_title': item_name,
    #                 'description': item_summary,
    #                 'is_product_or_service': True,
    #                 'form_type': 'lims',
    #                 'source': 'crawler'
    #             }
    #         )

    def _save_product_services(self, branch, products_services):
        for item in products_services:
            item_name = item.get('name')
            item_summary = item.get('summary', '')
            source_url = item.get('source_url', '')
            
            # Mappings: name -> is_number, summary -> is_title
            ProductService.objects.update_or_create(
                lab=branch,
                name=item_name,
                defaults={
                    'summary': item_summary,
                    'source_url': source_url                        
                }
            )
             
    @transaction.atomic
    def post(self, request, branch_id=None):
        # 1. Validate payload first
        serializer = LabCrawlerImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        # 2. Extract structured data
        result_data = data.get("result", {})
        structured_data = result_data.get("structured_data", {})
        contact_data = structured_data.get("contact_us", {})
        headquarter = contact_data.get("headquarter", {})
        social_links = contact_data.get("social_links", {})

        # 3. Extract values
        lab_name = (
            structured_data.get("lab_name")
            or structured_data.get("company_logo", {}).get("alt")
        )

        email = (headquarter.get("email") or "").strip()
        phones = headquarter.get("phone", [])
        primary_phone = phones[0] if phones else ""
        address_data = headquarter.get("address", {})
        full_address = address_data.get("full_address")
        website_url = structured_data.get("website")

        if not email or not lab_name:
            return Response(
                {
                    "error": "Missing essential fields (email or lab name)."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Resolve Branch and data
        branch = Branch.objects.filter(
            Q(website_url__iexact=website_url) |
            Q(lab_name__iexact=lab_name)
        ).first()

        if branch:
            created = False
            if not branch.lab_name or branch.lab_name.strip() == "":
                branch.lab_name = lab_name
            if not branch.contact_email or (isinstance(branch.contact_email, str) and branch.contact_email.strip() == ""):
                branch.contact_email = email
            if not branch.contact_mobile or (isinstance(branch.contact_mobile, str) and branch.contact_mobile.strip() == ""):
                branch.contact_mobile = primary_phone
            if not branch.source or (isinstance(branch.source, str) and branch.source.strip() == ""):
                branch.source = 'crawler'
            if not branch.lab_address or (isinstance(branch.lab_address, str) and branch.lab_address.strip() == ""):
                branch.lab_address = full_address
        else:
            branch = Branch(
                lab_name=lab_name,
                contact_email=email,
                contact_mobile=primary_phone,
                website_url=website_url,
                lab_address=full_address
            )
            created = True

        if structured_data.get("summary"):
            if not branch.description or (isinstance(branch.description, str) and branch.description.strip() == ""):
                branch.description = structured_data.get("summary")

        about_us_info = structured_data.get("about_us", {})
        if isinstance(about_us_info, dict) and about_us_info.get("summary"):
            if not branch.about_us or (isinstance(branch.about_us, str) and branch.about_us.strip() == ""):
                branch.about_us = about_us_info.get("summary")

        # save Logo
        logo_data = structured_data.get("company_logo", {})
        if isinstance(logo_data, dict):
            if not branch.lab_logo:
                self._save_crawler_logo(branch, logo_data)

        if len(phones) > 1:
            if not branch.land_line or (isinstance(branch.land_line, str) and branch.land_line.strip() == ""):
                branch.land_line = phones[1]

        branch.save()

        # -----------------------------------------------------------
        # 5. SAVE Social data
        # -----------------------------------------------------------
        if isinstance(social_links, dict):
            self._save_social_links(branch, social_links)

        # ------------------------------------------------------------
        # 6. SAVE PAGES DATA WITH MENU/SUBMENU TREE (LabWebPage)
        # ------------------------------------------------------------
        pages_tree = data.get('pages', [])
        self._save_page_tree(branch, pages_tree)

        # ------------------------------------------------------------
        # 7. SAVE ACCREDITATIONS (Accreditation & AccreditationMaster)
        # ------------------------------------------------------------
        accreditations = structured_data.get('accreditations', [])
        self._save_accreditations(branch, accreditations)

        # ------------------------------------------------------------
        # 8. SAVE PRODUCTS & SERVICES (BranchItem)
        # ------------------------------------------------------------
        products_services = structured_data.get('products_services', [])
        self._save_product_services(branch, products_services)

        action = "created" if created else "updated"
        return Response(
            {
                "status": "success",
                "message": f"Lab {action} successfully",
                "branch_id": str(branch.id),
                'name': lab_name,
                'contact_mobile': primary_phone,
                # 'branch': branch,
                'website': website_url,
                'lab_address': headquarter.get("address", {}).get("full_address"),
            },
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED
        )

class VistaSyncAPIView(APIView):
    """
    API endpoint to trigger fetching and syncing of branches from Vista.
    POST /vista-sync/
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            data = fetch_vista_branch_details()
            summary = sync_all_branches(data)
            return Response(
                {
                    "success": True,
                    "message": "Vista sync completed.",
                    "summary": summary
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BranchSearchAPIView(APIView):
    ''' Search for branches by name, org_name, or lab_code. Returns a list of matching branches. '''
    Authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        name = request.query_params.get('name', '').strip()

        if not name:
            return Response(
                {
                    "success": False,
                    "message": "Please provide a lab name to search.",
                    "data": []
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        branches = Branch.objects.filter(
            Q(lab_name__icontains=name)|
            Q(lab_name_hindi__icontains=name)|
            Q(org_name__icontains=name)|
            Q(lab_code=name)
        ).distinct()[:20]

        serializer = BranchSerializer(branches, many=True)

        return Response(
            {
                "success": True,
                "message": "Laboratories retrieved successfully.",
                "count": len(serializer.data),
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )


class ProductSearchAPIView(APIView):
    ''' Search for branches by product name. Returns a list of branches that offer the specified product. '''
    Authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        product = request.query_params.get('product', '').strip()

        if not product:
            return Response({
                "success": False,
                "message": "Please provide a product name to search.",
                "data": []
            }, status=status.HTTP_400_BAD_REQUEST)   

        branch_items = BranchItem.objects.filter(
            Q(is_number__icontains=product) |
            Q(is_title__icontains=product)
        ).values_list('lab_id', flat=True).distinct()

        # Get the branches/labs associated with matching products
        branches = Branch.objects.filter(
            id__in=branch_items
        ).distinct()

        serializer = BranchSerializer(branches, many=True)

        return Response({
            "success": True,
            "message": "Laboratories retrieved successfully.",
            "count": len(serializer.data),
            "data": serializer.data
        }, status=status.HTTP_200_OK)


def search_services_api(request):
    query = request.GET.get('q', '').strip()
    lab_id = request.GET.get('lab_id', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    # Base queryset for product/lab services
    queryset = ProductService.objects.all()

    # Optional: Filter by specific lab/branch if lab_id is provided
    if lab_id:
        queryset = queryset.filter(lab_id=lab_id)

    # # Search by IS Number, standard code, title, or service name
    # queryset = queryset.filter(
    #     Q(is_number__icontains=query) | 
    #     Q(is_title__icontains=query) |
    #     Q(name__icontains=query)
    # ).distinct()[:15]  # Limit results to 15 items for performance

    # Search by service name
    queryset = queryset.filter(
        Q(name__icontains=query)
    ).distinct()[:15]  # Limit results to 15 items for performance

    results = []
    for item in queryset:
        results.append({
            'id': item.pk,
            'number': getattr(item, 'is_number', '') or getattr(item, 'code', '') or item.name,
            'title': getattr(item, 'is_title', '') or getattr(item, 'description', '') or item.name,
        })

    return JsonResponse({'results': results})



def get_top_labs_api(request):
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()

    base_qs = Branch.objects.filter(is_active=True, is_public=True).prefetch_related(
        "branch_accreditation__accred",
        "lab_scope__certificate__accred",
        "lab_scope__facility_scope__certificate__accred"
        ).exclude(
            Q(lab_name__isnull=True) | Q(lab_name="")
        )

    if city or state:
        location_filter = Q()
        if city:
            location_filter |= Q(lab_city__icontains=city)
        if state:
            location_filter |= Q(lab_state__name__icontains=state)
            
        labs = base_qs.filter(location_filter)
        if not labs.exists():
            labs = base_qs
    else:
        labs = base_qs

    # labs = labs.order_by("-updated_at")[:24]
    labs_with_logo = [b for b in labs if b.lab_logo]
    labs_ordered = (labs_with_logo + [b for b in labs if not b.lab_logo])[:12]

    # Render labs using your partial HTML template
    html = render_to_string("includes/_lab_carousel_items.html", {"labs": labs_ordered}, request=request)
    return JsonResponse({"html": html})

