from django.test import Client, TestCase
from django.urls import reverse

from apps.labs.models import Branch, LabCategory
from apps.samples_configurations.models import Category, SubCategory
from apps.utility.models import Department, Discipline


class CategorySubCategoryAndDepartmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.email = "lab@test.com"
        self.branch = Branch.objects.create(
            lab_name="Precision Testing Lab",
            contact_email=self.email,
        )

        session = self.client.session
        session["registration_email"] = self.email
        session["email_verified"] = True
        session.save()

        # Disciplines & Departments
        self.disc_chem = Discipline.objects.create(name="Chemical Testing", code="CHEM")
        self.disc_mech = Discipline.objects.create(name="Mechanical Testing", code="MECH")

        self.dept_chem = Department.objects.create(
            name="Chemical Analysis",
            discipline=self.disc_chem,
        )
        self.dept_mech = Department.objects.create(
            name="Mechanical Physical",
            discipline=self.disc_mech,
        )

        # Categories & Subcategories
        self.cat_food = Category.objects.create(name="Food & Agriculture", order=1)
        self.cat_water = Category.objects.create(name="Water & Wastewater", order=2)

        self.sub_dairy = SubCategory.objects.create(
            name="Dairy Products",
            category=self.cat_food,
            order=1,
        )
        self.sub_spices = SubCategory.objects.create(
            name="Spices & Condiments",
            category=self.cat_food,
            order=2,
        )
        self.sub_drinking = SubCategory.objects.create(
            name="Packaged Drinking Water",
            category=self.cat_water,
            order=1,
        )

    def test_subcategory_model_relationship(self):
        """SubCategory belongs to Category and can be accessed through related_name."""
        self.assertEqual(self.sub_dairy.category, self.cat_food)
        self.assertIn(self.sub_dairy, self.cat_food.subcategories.all())
        self.assertIn(self.sub_spices, self.cat_food.subcategories.all())
        self.assertEqual(self.cat_food.subcategories.count(), 2)

    def test_department_independence_from_discipline(self):
        """
        Saving departments does not require or filter by discipline.
        Saving disciplines does not remove departments.
        """
        # Save a department (even if its discipline is not selected)
        resp = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_departments",
                "departments[]": ["Chemical Analysis", "Mechanical Physical"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.branch.departments.count(), 2)

        # Save only Chemical discipline - Mechanical department must NOT be removed!
        resp2 = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_disciplines",
                "disciplines[]": ["Chemical Testing"],
            },
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(self.branch.disciplines.count(), 1)
        # Mechanical department still exists because dependency is removed
        self.assertEqual(self.branch.departments.count(), 2)

    def test_save_categories_and_subcategories(self):
        """
        Saving categories associates them with the branch.
        Saving subcategories associates them with the branch.
        When category is removed, its subcategories are automatically cleaned up.
        """
        # 1. Select both Food and Water categories
        resp = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_categories",
                "categories[]": ["Food & Agriculture", "Water & Wastewater"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.branch.categories.count(), 2)

        # 2. Select subcategories
        resp2 = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_subcategories",
                "subcategories[]": ["Dairy Products", "Packaged Drinking Water"],
            },
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(self.branch.subcategories.count(), 2)

        # 3. Now deselect Water & Wastewater category (only Food remaining)
        resp3 = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_categories",
                "categories[]": ["Food & Agriculture"],
            },
        )
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(self.branch.categories.count(), 1)
        # Packaged Drinking Water subcategory should be cleaned up!
        self.assertEqual(self.branch.subcategories.count(), 1)
        self.assertEqual(self.branch.subcategories.first().name, "Dairy Products")

    def test_review_details_template_renders_categories_and_subcategories(self):
        """GET request renders categories and subcategories sections in review-details.html."""
        resp = self.client.get(reverse("lab-review-detail"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("categoriesWrap", content)
        self.assertIn("subcategoriesWrap", content)
        self.assertIn("Food &amp; Agriculture", content)
        self.assertIn("Dairy Products", content)

    def test_no_category_selected_means_no_subcategories_to_select(self):
        """
        When no categories are selected on the branch:
        1. Context display_subcategories is empty.
        2. review-details.html renders helper placeholder message.
        3. Attempting to save subcategories does not save any subcategory.
        """
        self.branch.categories.clear()
        self.branch.subcategories.clear()

        resp = self.client.get(reverse("lab-review-detail"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["display_subcategories"]), 0)
        self.assertIn("Please select a category above to view subcategories.", resp.content.decode("utf-8"))

        # Attempt to save subcategory while branch has no categories
        post_resp = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_subcategories",
                "subcategories[]": ["Dairy Products"],
            },
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertEqual(self.branch.subcategories.count(), 0)

    def test_lab_category_case1_and_case2_with_dynamic_schema(self):
        """
        Case 1: When lab_category is empty, user selecting category saves it,
        fetches dynamic schema fields, initializes category_data, and renders them.
        Dynamic field update: User edits dynamic fields and category_data is updated.
        Case 2: When user switches category, category_data is reset with new schema fields.
        """
        calib_cat = LabCategory.objects.create(
            name="Calibration Testing Lab",
            dynamic_schema={
                "title": "Calibration Lab Configuration",
                "fields": [
                    {"key": "onsite_testing_available", "type": "boolean", "label": "Onsite Testing Available", "required": True},
                    {"key": "calibration_charges_base", "type": "number", "label": "Base Calibration Charges", "required": True, "placeholder": "e.g. 500"},
                    {"key": "accreditation_details", "type": "text", "label": "ISO / NABL Accreditation Details", "required": True},
                ]
            }
        )
        path_cat = LabCategory.objects.create(
            name="Pathology Testing Lab",
            dynamic_schema={
                "title": "Pathology Lab Configuration",
                "fields": [
                    {"key": "home_collection_available", "type": "boolean", "label": "Home Collection Available", "required": True},
                    {"key": "home_collection_charges", "type": "number", "label": "Home Collection Charges (INR)", "required": False},
                ]
            }
        )

        # Ensure branch starts with no lab_category
        self.branch.lab_category = None
        self.branch.category_data = {}
        self.branch.save()

        # ── CASE 1: Assign category when branch.lab_category is empty ────────
        resp = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_general",
                "facility_lab_category": str(calib_cat.id),
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["category_id"], str(calib_cat.id))
        self.assertEqual(data["category_name"], calib_cat.name)
        self.assertEqual(len(data["fields"]), 3)
        self.assertIn("onsite_testing_available", data["category_data"])
        self.assertIn("calibration_charges_base", data["category_data"])

        self.branch.refresh_from_db()
        self.assertEqual(self.branch.lab_category, calib_cat)
        self.assertEqual(self.branch.category_data.get("onsite_testing_available"), False)
        self.assertEqual(self.branch.category_data.get("calibration_charges_base"), "")

        # Template renders the dynamic category fields
        get_resp = self.client.get(reverse("lab-review-detail"))
        self.assertEqual(get_resp.status_code, 200)
        content = get_resp.content.decode("utf-8")
        self.assertIn("sectionCategorySpecific", content)
        self.assertIn("dyn_onsite_testing_available", content)
        self.assertIn("dyn_calibration_charges_base", content)

        # ── LIVE DYNAMIC UPDATES: Update dynamic schema entries ───────────────
        dyn_save_resp = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_category_data",
                "category_data[onsite_testing_available]": "true",
                "category_data[calibration_charges_base]": "1250",
                "category_data[accreditation_details]": "ISO/IEC 17025",
            },
        )
        self.assertEqual(dyn_save_resp.status_code, 200)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.category_data["onsite_testing_available"], True)
        self.assertEqual(self.branch.category_data["calibration_charges_base"], "1250")
        self.assertEqual(self.branch.category_data["accreditation_details"], "ISO/IEC 17025")

        # ── CASE 2: Switch category from Calibration Lab to Pathology Lab ────
        resp2 = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_general",
                "facility_lab_category": str(path_cat.id),
            },
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["status"], "success")
        self.assertEqual(data2["category_id"], str(path_cat.id))
        self.assertEqual(data2["category_name"], path_cat.name)
        self.assertEqual(len(data2["fields"]), 2)
        # Previous calibration keys wiped; new pathology keys initialized
        self.assertIn("home_collection_available", data2["category_data"])
        self.assertNotIn("onsite_testing_available", data2["category_data"])

        self.branch.refresh_from_db()
        self.assertEqual(self.branch.lab_category, path_cat)
        self.assertIn("home_collection_available", self.branch.category_data)
        self.assertNotIn("onsite_testing_available", self.branch.category_data)

        # Live dynamic updates on new pathology fields
        dyn_save_resp2 = self.client.post(
            reverse("lab-review-detail"),
            {
                "action": "save_category_data",
                "category_data[home_collection_available]": "true",
                "category_data[home_collection_charges]": "200",
            },
        )
        self.assertEqual(dyn_save_resp2.status_code, 200)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.category_data["home_collection_available"], True)
        self.assertEqual(self.branch.category_data["home_collection_charges"], "200")
