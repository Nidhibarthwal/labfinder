# Programmatic SEO (pSEO) Engine for LabFinder

A scalable, database-driven Programmatic SEO (pSEO) engine designed for LabFinder to automatically create, manage, and bulk-update high-ranking landing pages (e.g., *"Top 5 Food Testing Labs in Delhi"*, *"Top 5 Soil and Rock Labs in Hyderabad"*, *"Top 5 Calibration Labs in Ghaziabad"*).

This architecture mirrors the programmatic landing page registries used by marketplace platforms like **IndiaMART, Alibaba, Practo, and Justdial**.

---

## Table of Contents
1. [Core Problem & Architecture](#core-problem--architecture)
2. [Data Model Mapping](#data-model-mapping)
3. [Database Models](#database-models)
4. [Bulk Generation Engine](#bulk-generation-engine)
5. [Bulk Metadata Updates in the Future](#bulk-metadata-updates-in-the-future)
6. [Crawler Discovery & Google Ranking](#crawler-discovery--google-ranking)
7. [Management Commands Cheat Sheet](#management-commands-cheat-sheet)
8. [Admin Features](#admin-features)
9. [Automated Signals](#automated-signals)
10. [Testing](#testing)

---

## 1. Core Problem & Architecture

### Why not pure regex URL patterns like `/top-5-<category>-labs-in-<city>/`?
- **The "Thin Content / Soft-404" Penalty**: If a crawler visits a combination where zero or few labs exist (e.g., *"Top 5 Marine Testing Labs in Meerut"*), Google flags the page as low-quality or thin content, damaging your entire domain's search ranking.
- **Crawl Budget Exhaustion**: Search engine bots will waste crawl quota requesting empty permutations.
- **Lack of Bulk Editability**: Hardcoded regex patterns cannot easily have customized meta titles, unique FAQ rich snippets, or custom marketing copy stored in the database.

### The Solution: Database-Backed Landing Page Registry
1. Every published SEO URL has a persistent record in `SEOLandingPage`.
2. A page is **only active/published when real, verified laboratories exist** ($\ge 1$).
3. SEO tags (Title, Description, H1, Keywords, FAQ Schema) are rendered from a centralized pattern engine (`SEOTemplate`) and saved directly into the database.
4. Changing a template allows updating **thousands of pages in seconds** via bulk database updates.
5. All active pages are automatically published to Google via an automated XML Sitemap (`/sitemap.xml`).

---

## 2. Data Model Mapping

The SEO engine directly uses the core database fields as requested:

| Entity | Source Table in LabFinder | Purpose in SEO Engine |
| :--- | :--- | :--- |
| **Category** | `apps.samples_configurations.models.Category` (L98) | Primary category classification (e.g. *Food Testing*, *Calibration*, *Water & Environment*) |
| **Lab Category M2M** | `Branch.categories` (`ManyToManyField(Category)`) | Maps laboratories directly to their primary categories |
| **Group Name** | `Branch.group_name` (`TextField`, L271) | Specific testing specialty (e.g. *Soil and Rock*, *Building Materials*, *Solid Fuels*, *Petroleum and Products*) |
| **Location** | `Branch.lab_city`, `Branch.lab_state` (L289-L297) | Geographic classification across 700+ Indian cities |

---

## 3. Database Models

### `SEOTemplate` (`apps.seo.models.SEOTemplate`)
Stores dynamic pattern formulas for generating meta tags and schema markup.

- `page_type`: Choice field (e.g., `category_city`, `category_state`, `city_only`).
- `title_pattern`: Format string.  
  *Default:* `"Top {count} {category} Labs in {location} (NABL Accredited) | LabFinder"`
- `meta_desc_pattern`: Format string for Google SERP snippet.  
  *Default:* `"Find and compare top {count} {category_phrase} laboratories in {location}. View NABL & BIS accreditations, testing turnaround times, sample parameters, and request instant quotation on LabFinder."`
- `h1_pattern`: Format string for page heading.  
  *Default:* `"Top {count} {category_phrase} Laboratories in {location}"`
- `intro_pattern`: Introduction copy summarizing testing in that location.
- `faq_pattern`: List of questions & answers with `{category}`, `{location}`, `{count}` placeholders.

> **Grammar Handling**: The engine automatically detects category naming (e.g. *"Food Testing"* vs *"Calibration"*), creating clean phrases like *"Food Testing Laboratories"* instead of repeating *"Food Testing Testing Laboratories"*.

---

### `SEOLandingPage` (`apps.seo.models.SEOLandingPage`)
Stores the actual programmatic landing page rendered on the website.

```python
class SEOLandingPage(models.Model):
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    page_type = models.CharField(max_length=50, default="category_city", db_index=True)

    # 1. Category Reference (apps.samples_configurations.models.Category)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="seo_landing_pages",
        null=True,
        blank=True
    )

    # 2. Group Reference (Branch.group_name)
    group_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    # 3. Location Reference (Branch.lab_city)
    city = models.CharField(max_length=255, db_index=True)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    region = models.CharField(max_length=100, blank=True, null=True)

    # SEO Metadata
    meta_title = models.CharField(max_length=255)
    meta_description = models.TextField()
    meta_keywords = models.CharField(max_length=255, blank=True)
    h1_heading = models.CharField(max_length=255)
    intro_content = models.TextField(blank=True)
    faq_schema = models.JSONField(default=list, blank=True)

    # Metrics & Publish State
    lab_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_customized = models.BooleanField(default=False)
```

#### Why there is NO redundant `category_name` text column:
- When a page is based on a **Category**, `self.category.name` is accessed directly via the ForeignKey to `Category`.
- When a page is based on a **Group Name**, `self.group_name` directly stores the group string from `Branch.group_name`.
- The model provides a dynamic property:
  ```python
  @property
  def display_category(self):
      if self.category_id:
          return self.category.name
      return self.group_name or "Testing"
  ```
  This eliminates duplicate denormalized text columns, prevents data drift, and ensures clean database normalization.

---

## 4. Bulk Generation Engine

The generator engine (`apps.seo.services.generate_bulk_seo_pages`) uses a **2-Pass Architecture**:

### Pass 1: Formal Category Pages (`Branch.categories`)
1. Automatically synchronizes laboratory categories based on `Branch.group_name`, `discipline_name`, and `lab_category`.
2. Scans all active `Category` instances.
3. Finds every distinct city where matching labs exist.
4. Generates pages with `page_type="category_city"` and links `page.category = cat`.
   - *Example:* `/labs/top-5-food-testing-labs-in-delhi/`
   - *Example:* `/labs/top-5-water-environment-labs-in-mumbai/`

### Pass 2: Specialized Testing Group Pages (`Branch.group_name`)
1. Scans distinct prominent testing specialties from `Branch.group_name` (e.g. *Soil and Rock*, *Buildings Materials*, *Solid Fuels*, *Petroleum and Products*, *Plastics and Plastic Products*, *Rubber and Rubber Products*, *Ores & Minerals*).
2. For each distinct city where labs with that specialty exist:
3. Generates pages with `page_type="group_city"` and stores `page.group_name = g_name`.
   - *Example:* `/labs/top-5-soil-and-rock-labs-in-hyderabad/`
   - *Example:* `/labs/top-5-buildings-materials-labs-in-mumbai/`
   - *Example:* `/labs/top-5-solid-fuels-labs-in-kolkata/`

### Running Bulk Generation via CLI:
```bash
python manage.py generate_seo_pages
```

*Options:*
- `--min-labs <number>`: Minimum number of verified labs required to publish a page (default: `1`). Pages with fewer labs are marked `is_active=False`.
- `--overwrite-customized`: Forces regeneration even on manually edited pages.

---

## 5. Bulk Metadata Updates in the Future

When you need to update SEO metadata across thousands of existing pages (e.g. updating branding, adding the year `2026`, or changing call-to-actions):

### Method A: CLI Bulk Re-rendering (Fastest)
1. Edit the template patterns in `SEOTemplate` (via Django Admin or shell).
2. Run:
   ```bash
   python manage.py update_seo_metadata
   ```
   *Options:*
   - `--page-type <type>`: Target specific page type (e.g., `category_city`, `group_city`).
   - `--force`: Overwrite customized pages as well.

> Uses Django's `bulk_update(batch_size=1000)`: Updates 50,000+ records in under 5 seconds.

### Method B: Django Admin Bulk Actions
1. Navigate to `/admin/seo/seolandingpage/`.
2. Select the desired landing pages.
3. Choose the action: **"Regenerate SEO metadata from active template for selected pages"**.
4. Click **Go**.

### Method C: CSV Export / Import for Marketing Teams
1. In Django Admin, select pages and choose **"Export selected pages as CSV for SEO & Marketing teams"**.
2. Edit titles/descriptions in Excel / Google Sheets.
3. Import back into the system with `is_customized=True` to preserve your bespoke copy.

---

## 6. Crawler Discovery & Google Ranking

Search engines discover and rank these pages through three integrated channels:

### 1. Google XML Sitemap Architecture (`/sitemap.xml`)
Configured in `apps.seo.sitemaps` and wired into `config.urls`. The platform provides both a unified master sitemap and sectioned sub-sitemaps for granular crawl management:

- **`/sitemap.xml`**: Consolidated master sitemap containing all indexable URLs across the entire platform.
- **`/sitemap-static.xml` (`StaticViewSitemap`)**: Core public pages:
  - Homepage (`/`) with priority `1.0` and `daily` change frequency.
  - Lab Search (`/search/lab/`) with priority `0.9` and `daily` change frequency.
  - Product Search (`/search/product/`) with priority `0.9` and `daily` change frequency.
  - Enquiry Now (`/enquiry_now`) with priority `0.8` and `weekly` change frequency.
- **`/sitemap-seo.xml` (`SEOLandingPageSitemap`)**:
  - Programmatic Category x City landing pages (`/labs/top-5-food-testing-labs-in-delhi/`, etc.).
  - Automatically filters out pages where `lab_count == 0` (preventing soft 404 penalties).
  - Priority `0.8`, `weekly` change frequency, with live `<lastmod>` timestamps.
- **`/sitemap-labs.xml` (`LabDetailSitemap`)**:
  - Individual profile pages for verified laboratories (`/lab-detail/<slug>/`, e.g. `/lab-detail/ghaziabad-testing-lab/`).
  - Filters `is_active=True` and `is_public=True`.
  - Canonical 301 permanent redirects from legacy UUID URLs (`/lab-detail/<uuid>/`) to human-readable SEO slugs.
  - Priority `0.7`, `weekly` change frequency, with `<lastmod>` timestamps.
- **`/robots.txt`**: Automatically points crawlers to `/sitemap.xml` while disallowing internal private areas (`/admin/`, `/api/`, `/lead/`, `/order/`, `/dashboard/`, `/crawler-dashboard/`).

### 2. Internal Linking Grid (IndiaMART Strategy)
Every landing page (`templates/seo/landing_page.html`) renders dynamic link grids at the bottom:
- **"Other Popular Testing Categories in {City}"**: Links to other category landing pages in the same city.
- **"{Category} Testing Laboratories in Other Cities"**: Links to the same category across other industrial hubs.

This creates an interconnected spiderweb of internal links, ensuring Googlebot indexes all pages without orphan URLs.

### 3. Structured Data (JSON-LD)
Every landing page automatically outputs valid Schema.org structured data in `<head>`:
- **`BreadcrumbList`**: Displays breadcrumb trails (`Home > Testing Labs in Delhi > Top 5 Food Testing Labs`) in Google search results.
- **`ItemList`**: Outlines the top laboratories with names, addresses, and profile links.
- **`FAQPage`**: Renders questions and answers directly into Google's expandable accordion search snippets.

---

## 7. Management Commands Cheat Sheet

| Command | Purpose | Example |
| :--- | :--- | :--- |
| `generate_seo_pages` | Scan DB and create/update all category x city and group x city pages | `python manage.py generate_seo_pages --min-labs=1` |
| `update_seo_metadata` | Re-render metadata across all pages from active template | `python manage.py update_seo_metadata --page-type=category_city` |
Make changes in SEOTemplate and run above command. This command is used to update records in bulk
---
### Agar 50,000 mein se sirf 10,000 Pages Update Karne Hon?
README mein `update_seo_metadata` ke liye sirf `--page-type` aur `--force` options diye gaye hain[cite: 1]—isliye **50,000 mein se sirf 10,000 pages** target karne ke liye aapko command mein filter options add karne honge (jaise `--city`, `--category`, `--state`, ya `--limit`).

#### Practical Tareeke (Subset / 10,000 Pages):

 **Location / Category Filter se Subset Banana (Sabse Natural Tareeka):**
   Agar 50,000 pages mein se lagbhag 10,000 pages kisi specific state, region, ya category ke hain, toh command mein wahi filter pass karo:
   ```bash
   # Example: If you want to update pages of any specific city (Delhi / UP) or any specific category
   python manage.py update_seo_metadata --page-type=category_city --city="Delhi"
   or you can add flag like --category-slug=food-testing 

## 8. Admin Features

Accessible at `/admin/seo/`:
- **SEO Templates**: Edit title and description pattern formulas without changing code.
- **SEO Landing Pages**:
  - Filter by `Category`, `Group Name`, `City`, `is_active`, and `is_customized`.
  - Search by slug, city name, meta title, or heading.
  - Bulk actions:
    - *Regenerate SEO metadata from active template*
    - *Activate selected pages*
    - *Deactivate selected pages*
    - *Export selected pages as CSV*

---

## 9. Automated Signals

Located in `apps.seo.signals`:
- **`on_branch_save_sync_seo`**: When a `Branch` (laboratory) is created or its location changes, the corresponding landing page is automatically created/updated.
- **`on_branch_categories_changed_sync_seo`**: When categories are added/removed on a lab, counts and publish statuses are refreshed automatically.

---

## 10. Testing

Run the full automated test suite:
```bash
python manage.py test apps.seo
```

Verifies:
1. Fresh bulk generation from `Category`, `Branch.categories`, and `Branch.group_name`.
2. Public landing page rendering (200 OK) with `<title>`, meta tags, and structured JSON-LD.
3. Mass metadata updates via `update_bulk_seo_metadata`.
4. XML Sitemap output (`/sitemap.xml`, `/sitemap-seo.xml`, `/sitemap-static.xml`, `/sitemap-labs.xml`).
5. Automated signals when a new laboratory registers.
