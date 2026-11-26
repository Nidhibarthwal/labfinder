document.addEventListener("DOMContentLoaded", () => {
    const getCsrfToken = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";

    const UNDER_REVIEW_MSG = "Your lab profile has already been submitted and is currently being reviewed for approval. Updates are disabled while under review.";
    let lastReviewAlertAt = 0;

    function isUnderReview() {
        const btn = document.getElementById("btnSubmitApproval");
        return ((btn?.dataset?.labStatus || "").toLowerCase() === "reviewed");
    }

    function showUnderReviewAlert() {
        const now = Date.now();
        if (now - lastReviewAlertAt < 1500) return;
        lastReviewAlertAt = now;
        if (typeof window.showSiteToast === "function") {
            window.showSiteToast(UNDER_REVIEW_MSG, "warning");
        } else {
            alert(UNDER_REVIEW_MSG);
        }
    }

    if (isUnderReview()) {
        document.addEventListener("change", (e) => {
            if (e.target.closest("main") || e.target.closest(".product-modal") || e.target.closest(".review-card")) {
                showUnderReviewAlert();
            }
        }, true);

        document.addEventListener("submit", (e) => {
            if (e.target.closest("main") || e.target.closest(".product-modal")) {
                e.preventDefault();
                e.stopImmediatePropagation();
                showUnderReviewAlert();
            }
        }, true);
    }

    async function sendAutoSave(action, formData) {
        if (isUnderReview()) {
            showUnderReviewAlert();
            return { status: "error", message: UNDER_REVIEW_MSG };
        }
        const csrfToken = getCsrfToken();
        formData.append("action", action);
        formData.append("csrfmiddlewaretoken", csrfToken);
        try {
            const response = await window.fetch(window.location.href, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            return await response.json();
        } catch (err) {
            console.error(`Auto-save error [${action}]:`, err);
            return null;
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // -------------------------------------------------------------------------
    // 1. Stepper Navigation
    // -------------------------------------------------------------------------
    const stepLinks = document.querySelectorAll(".review-step");
    const sections = [
        { el: document.getElementById("sectionBasicInfo"), step: document.getElementById("stepBasicInfo") },
        { el: document.getElementById("sectionAbout"), step: document.getElementById("stepAbout") },
        { el: document.getElementById("sectionAccreditations"), step: document.getElementById("stepAccreditations") },
        { el: document.getElementById("sectionScope"), step: document.getElementById("stepScope") },
    ];

    stepLinks.forEach((link) => {
        link.addEventListener("click", (e) => {
            const targetId = link.getAttribute("href");
            if (targetId && targetId.startsWith("#")) {
                const targetEl = document.querySelector(targetId);
                if (targetEl) {
                    e.preventDefault();
                    const header = document.querySelector(".header--auth");
                    const headerHeight = header ? header.offsetHeight : 80;
                    const offsetPosition = Math.max(0, targetEl.getBoundingClientRect().top + window.scrollY - headerHeight - 24);
                    window.scrollTo({ top: offsetPosition, behavior: "smooth" });
                    stepLinks.forEach((s) => s.classList.remove("review-step--active"));
                    link.classList.add("review-step--active");
                }
            }
        });
    });

    window.addEventListener("scroll", () => {
        const scrollPos = window.scrollY + 180;
        sections.forEach(({ el, step }) => {
            if (el && step && scrollPos >= el.offsetTop && scrollPos < el.offsetTop + el.offsetHeight) {
                stepLinks.forEach((s) => s.classList.remove("review-step--active"));
                step.classList.add("review-step--active");
            }
        });
    }, { passive: true });

    // -------------------------------------------------------------------------
    // 2. Social Media Links Dropdown & Auto-Save
    // -------------------------------------------------------------------------
    const socialHeader   = document.getElementById("socialMediaHeader");
    const socialCard     = document.getElementById("socialMediaCard");
    const socialDropdown = document.getElementById("socialMediaDropdown");
    const socialIcons    = document.getElementById("socialMediaIcons");

    function openSocialDropdown() {
        if (!socialDropdown) return;
        socialDropdown.closest(".review-section")?.classList.add("review-section--elevated");
        socialDropdown.removeAttribute("hidden");
        socialCard?.setAttribute("aria-expanded", "true");
        socialCard?.classList.add("is-open");
        socialHeader?.setAttribute("aria-expanded", "true");
    }

    function closeSocialDropdown() {
        if (!socialDropdown) return;
        socialDropdown.closest(".review-section")?.classList.remove("review-section--elevated");
        socialDropdown.setAttribute("hidden", "");
        socialCard?.setAttribute("aria-expanded", "false");
        socialCard?.classList.remove("is-open");
        socialHeader?.setAttribute("aria-expanded", "false");
    }

    socialCard?.addEventListener("click", (e) => {
        if (!socialDropdown || socialDropdown.contains(e.target) || e.target.closest(".review-social-btn")) return;
        socialDropdown.hasAttribute("hidden") ? openSocialDropdown() : closeSocialDropdown();
    });

    socialDropdown?.addEventListener("change", async (e) => {
        if (!e.target.matches("input[name='social_url']")) return;
        const fd = new FormData();
        const html = [];

        socialDropdown.querySelectorAll(".review-social-dropdown__row").forEach(row => {
            const platform = row.querySelector("input[name='social_platform']")?.value;
            const url = row.querySelector("input[name='social_url']")?.value?.trim();
            if (platform && url && url !== "https://") {
                fd.append("social_platform", platform);
                fd.append("social_url", url);
                html.push(`
                    <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="review-social-btn" aria-label="${escapeHtml(platform)}">
                        <img src="/static/images/social_${escapeHtml(platform)}.svg" alt="${escapeHtml(platform)}" width="30" height="30">
                    </a>
                `);
            }
        });

        if (socialIcons) {
            socialIcons.innerHTML = html.length ? html.join("") : "<p>No social media links available. Add some below.</p>";
        }
        await sendAutoSave("save_socials", fd);
    });

    // -------------------------------------------------------------------------
    // 3. Inline Auto-Search & Select/Unselect Tag Boxes
    // -------------------------------------------------------------------------
    const PLUS_PATH  = "M8 3.5V12.5M3.5 8H12.5";
    const MINUS_PATH = "M3.5 8H12.5";

    const tagGroups = {
        discipline: {
            idAttr: "disciplineId",
            dataAttrName: "data-discipline-id",
            box: document.getElementById("disciplinesBox"),
            input: document.getElementById("disciplinesSearchInput"),
            selectedWrap: document.getElementById("disciplinesSelectedWrap"),
            suggestionsWrap: document.getElementById("disciplinesSuggestionsWrap"),
            action: "save_disciplines",
            fieldName: "disciplines[]",
            defaultLimit: 4
        },
        department: {
            idAttr: "departmentId",
            dataAttrName: "data-department-id",
            box: document.getElementById("testingTypesBox"),
            input: document.getElementById("typesSearchInput"),
            selectedWrap: document.getElementById("testingTypesSelectedWrap"),
            suggestionsWrap: document.getElementById("testingTypesSuggestionsWrap"),
            action: "save_departments",
            fieldName: "departments[]",
            defaultLimit: 4
        },
        category: {
            idAttr: "categoryId",
            dataAttrName: "data-category-id",
            box: document.getElementById("categoriesBox"),
            input: document.getElementById("categoriesSearchInput"),
            selectedWrap: document.getElementById("categoriesSelectedWrap"),
            suggestionsWrap: document.getElementById("categoriesSuggestionsWrap"),
            action: "save_categories",
            fieldName: "categories[]",
            defaultLimit: 4
        },
        subcategory: {
            idAttr: "subcategoryId",
            dataAttrName: "data-subcategory-id",
            box: document.getElementById("subcategoriesBox"),
            input: document.getElementById("subcategoriesSearchInput"),
            selectedWrap: document.getElementById("subcategoriesSelectedWrap"),
            suggestionsWrap: document.getElementById("subcategoriesSuggestionsWrap"),
            action: "save_subcategories",
            fieldName: "subcategories[]",
            defaultLimit: 4
        }
    };

    function getSelectedCategoryIds() {
        const wrap = tagGroups.category.selectedWrap;
        if (!wrap) return new Set();
        return new Set(
            Array.from(wrap.querySelectorAll(".review-tag-pill"))
                .map(el => String(el.dataset.categoryId || "").trim())
                .filter(Boolean)
        );
    }

    function setPillVisualState(pill, isSelected) {
        pill.classList.toggle("review-tag-pill--selected", isSelected);
        pill.setAttribute("aria-pressed", String(isSelected));
        const svg = pill.querySelector("svg");
        if (svg) {
            svg.setAttribute("viewBox", "0 0 16 16");
            svg.innerHTML = `<path d="${isSelected ? MINUS_PATH : PLUS_PATH}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`;
        }
    }

    function showChip(chip, visible) {
        chip.hidden = !visible;
        chip.style.display = visible ? "inline-flex" : "none";
    }

    function renderTagSuggestions(groupKey) {
        const group = tagGroups[groupKey];
        if (!group || !group.suggestionsWrap) return;

        const query = (group.input?.value || "").trim().toLowerCase();
        const selectedIds = new Set(
            Array.from(group.selectedWrap?.querySelectorAll(".review-tag-pill") || [])
                .map(el => String(el.dataset[group.idAttr] || "").trim())
        );

        const selectedCatIds = groupKey === "subcategory" ? getSelectedCategoryIds() : null;
        const subcatCard = document.getElementById("subcategoriesCard");
        if (groupKey === "subcategory" && subcatCard) {
            subcatCard.style.display = selectedCatIds.size === 0 ? "none" : "";
        }

        let shownCount = 0;
        group.suggestionsWrap.querySelectorAll(".review-tag-pill").forEach(chip => {
            const id = String(chip.dataset[group.idAttr] || "").trim();
            const name = (chip.getAttribute("data-tag") || chip.textContent || "").trim().toLowerCase();

            if (selectedIds.has(id)) {
                showChip(chip, false);
                return;
            }
            if (groupKey === "subcategory" && !selectedCatIds.has(String(chip.dataset.categoryId || "").trim())) {
                showChip(chip, false);
                return;
            }

            if (query.length > 0) {
                showChip(chip, name.includes(query));
            } else {
                const canShow = shownCount < group.defaultLimit;
                showChip(chip, canShow);
                if (canShow) shownCount++;
            }
        });
    }

    async function saveTagGroup(groupKey) {
        const group = tagGroups[groupKey];
        if (!group || !group.selectedWrap) return;
        const formData = new FormData();
        group.selectedWrap.querySelectorAll(".review-tag-pill").forEach(chip => {
            const tagVal = (chip.getAttribute("data-tag") || chip.textContent || "").trim();
            if (tagVal) formData.append(group.fieldName, tagVal);
        });
        await sendAutoSave(group.action, formData);
    }

    Object.entries(tagGroups).forEach(([key, group]) => {
        group.box?.addEventListener("click", (e) => {
            if (!e.target.closest(".review-tag-pill")) group.input?.focus();
        });
        group.input?.addEventListener("input", () => renderTagSuggestions(key));
        group.input?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const firstMatch = Array.from(group.suggestionsWrap?.querySelectorAll(".review-tag-pill") || [])
                    .find(chip => !chip.hidden && chip.style.display !== "none");
                if (firstMatch) firstMatch.click();
            }
        });
        renderTagSuggestions(key);
    });

    // -------------------------------------------------------------------------
    // 4. Accreditations & Detailed Services (Add & Auto-Save)
    // -------------------------------------------------------------------------
    const servicesList        = document.getElementById("servicesList");
    const btnAddService       = document.getElementById("btnAddService");
    const btnEmptyAddServices = document.getElementById("btnEmptyAddServices");
    const accredList          = document.getElementById("accreditationsList");
    const btnAddCert          = document.getElementById("btnAddCertificate");

    function addServiceCard() {
        if (!servicesList) return;
        const card = document.createElement("article");
        card.className = "review-service-card review-service-card--active";
        card.innerHTML = `
            <button type="button" class="review-dismiss-btn" title="Remove Service" aria-label="Remove Service">
                <svg width="8" height="8" viewBox="3.4 3.4 6.8 6.8" fill="none" aria-hidden="true"><path d="M4.35478 10.2004L3.40039 9.246L5.85453 6.79187L3.40039 4.35478L4.35478 3.40039L6.80891 5.85453L9.246 3.40039L10.2004 4.35478L7.74626 6.79187L10.2004 9.246L9.246 10.2004L6.80891 7.74626L4.35478 10.2004Z" fill="#4F576D"/></svg>
            </button>
            <input type="text" name="name" class="review-service-input-title" placeholder="Add Service Title" aria-label="Service Title">
            <textarea name="service_description" class="review-service-input-desc" placeholder="Add Description" aria-label="Service Description"></textarea>
        `;
        servicesList.appendChild(card);
        card.querySelector(".review-service-input-title")?.focus();
    }

    btnAddService?.addEventListener("click", addServiceCard);
    btnEmptyAddServices?.addEventListener("click", addServiceCard);

    async function saveServiceCard(card) {
        if (!card) return;
        const nameInput = card.querySelector(".review-service-input-title, .review-service-card__title");
        const descInput = card.querySelector(".review-service-input-desc, .review-service-card__desc");
        const name = (nameInput?.value ?? nameInput?.textContent ?? "").trim();
        const desc = (descInput?.value ?? descInput?.textContent ?? "").trim();
        if (!name) return;

        const formData = new FormData();
        if (card.dataset.id) formData.append("service_id", card.dataset.id);
        formData.append("name", name);
        formData.append("service_description", desc);
        const res = await sendAutoSave("save_services", formData);
        if (res?.service_id) card.dataset.id = res.service_id;
    }

    function addAccreditationRow() {
        if (!accredList) return;
        const row = document.createElement("div");
        row.className = "review-accreditation-row";
        row.innerHTML = `
            <button type="button" class="review-dismiss-btn" title="Remove Certificate" aria-label="Remove Certificate">
                <svg width="8" height="8" viewBox="3.4 3.4 6.8 6.8" fill="none" aria-hidden="true"><path d="M4.35478 10.2004L3.40039 9.246L5.85453 6.79187L3.40039 4.35478L4.35478 3.40039L6.80891 5.85453L9.246 3.40039L10.2004 4.35478L7.74626 6.79187L10.2004 9.246L9.246 10.2004L6.80891 7.74626L4.35478 10.2004Z" fill="#4F576D"/></svg>
            </button>
            <label class="review-accred-logo-box" title="Click to upload certificate logo">
                <img src="/static/images/workspace_premium.svg" alt="Certificate Badge" width="30" height="42">
                <input type="file" class="review-accred-logo-input" name="accreditation_logo" accept="image/*">
            </label>
            <div class="review-accred-field review-accred-field--body">
                <label class="review-accred-field-label">Body / Standard</label>
                <div class="review-accred-field-value"><input type="text" class="review-accred-input" name="accreditation_body" placeholder="e.g. ISO 9001:2015"></div>
            </div>
            <div class="review-accred-field review-accred-field--cert">
                <label class="review-accred-field-label">Certificate No.</label>
                <div class="review-accred-field-value"><input type="text" class="review-accred-input" name="certificate_no" placeholder="e.g. TC-8894"></div>
            </div>
            <div class="review-accred-field review-accred-field--validity">
                <span class="review-accred-field-label">Validity</span>
                <div class="review-accred-field-value"><span class="review-accred-field-text">DD/MM/YYYY</span></div>
                <input type="date" class="review-accred-date-input" name="validity_date">
            </div>
        `;
        accredList.appendChild(row);
        row.querySelector(".review-accred-input")?.focus();
    }

    btnAddCert?.addEventListener("click", addAccreditationRow);

    async function saveAccredRow(row) {
        if (!row) return;
        const body = row.querySelector("[name='accreditation_body']")?.value.trim() || "";
        const certNo = row.querySelector("[name='certificate_no']")?.value.trim() || "";
        const validity = row.querySelector("[name='validity_date']")?.value || "";
        const logoInput = row.querySelector(".review-accred-logo-input");
        if (!body && !certNo) return;

        const formData = new FormData();
        if (row.dataset.id) formData.append("accred_id", row.dataset.id);
        formData.append("accreditation_body", body);
        formData.append("certificate_no", certNo);
        formData.append("validity_date", validity);
        if (logoInput?.files?.[0]) formData.append("accreditation_logo", logoInput.files[0]);

        const res = await sendAutoSave("save_accreditation", formData);
        if (res?.accred_id) row.dataset.id = res.accred_id;
    }

    document.addEventListener("blur", async (e) => {
        if (e.target.matches(".review-service-input-title, .review-service-input-desc")) {
            await saveServiceCard(e.target.closest(".review-service-card"));
        } else if (e.target.matches(".review-accred-input")) {
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        }
    }, true);

    document.addEventListener("change", async (e) => {
        if (e.target.matches(".review-accred-date-input")) {
            const val = e.target.value;
            const textSpan = e.target.closest(".review-accred-field--validity")?.querySelector(".review-accred-field-text");
            if (textSpan) {
                textSpan.textContent = val ? val.split("-").reverse().join("/") : "DD/MM/YYYY";
            }
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        } else if (e.target.matches(".review-accred-logo-input") && e.target.files?.[0]) {
            const img = e.target.closest(".review-accred-logo-box")?.querySelector("img");
            if (img) img.src = URL.createObjectURL(e.target.files[0]);
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        } else if (e.target.id === "selectAllStandards") {
            const isChecked = e.target.checked;
            document.querySelectorAll("#psTableBody .ps-checkbox").forEach(cb => { cb.checked = isChecked; });
        }
    });

    // -------------------------------------------------------------------------
    // 5. General Fields, Logo & Facility Photos Auto-Save
    // -------------------------------------------------------------------------
    function getGeneralInputs() {
        return Array.from(document.querySelectorAll("#sectionBasicInfo input:not([type=file]), #sectionBasicInfo select, #sectionAbout textarea"))
            .filter(el => !el.closest("#socialMediaDropdown") && !el.classList.contains("dynamic-category-input") && !el.classList.contains("review-tag-box__input"));
    }

    getGeneralInputs().forEach(input => {
        input.addEventListener("change", async () => {
            const formData = new FormData();
            getGeneralInputs().forEach(el => { if (el.name) formData.append(el.name, el.value); });
            await sendAutoSave("save_general", formData);
        });
    });

    const logoInput   = document.getElementById("logoUploadInput");
    const logoInitial = document.getElementById("logoInitialText");

    logoInput?.addEventListener("change", async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        let logoImg = document.getElementById("logoPreviewImg");
        if (!logoImg) {
            logoImg = document.createElement("img");
            logoImg.id = "logoPreviewImg";
            logoImg.alt = "Lab Logo Preview";
            logoImg.className = "review-logo-preview-img";
            logoInput.parentElement?.insertBefore(logoImg, logoInput);
        }
        logoImg.src = URL.createObjectURL(file);
        logoImg.style.display = "block";
        if (logoInitial) logoInitial.style.display = "none";

        const formData = new FormData();
        formData.append("lab_logo", file);
        await sendAutoSave("save_general", formData);
    });

    const photoInput = document.getElementById("facilityPhotoInput");

    function updatePhotoPlaceholders() {
        const grid = document.querySelector(".review-photos-grid");
        if (!grid) return;
        const photoCount = grid.querySelectorAll(".review-photo-slot").length;
        const remainingNeeded = Math.max(0, 4 - photoCount);
        const placeholders = Array.from(grid.querySelectorAll(".review-photo-placeholder-slot"));

        while (placeholders.length < remainingNeeded) {
            const slot = document.createElement("div");
            slot.className = "review-photo-placeholder-slot";
            slot.setAttribute("aria-hidden", "true");
            grid.appendChild(slot);
            placeholders.push(slot);
        }
        placeholders.forEach((slot, index) => {
            slot.style.display = index < remainingNeeded ? "" : "none";
        });
    }

    updatePhotoPlaceholders();

    photoInput?.addEventListener("change", async (e) => {
        const files = e.target.files;
        if (!files?.length) return;
        const formData = new FormData();
        Array.from(files).forEach(f => formData.append("facility_photos", f));
        const res = await sendAutoSave("upload_photo", formData);
        if (res?.status === "success" && res.photos) {
            const grid = document.querySelector(".review-photos-grid");
            const firstPlaceholder = grid?.querySelector(".review-photo-placeholder-slot");
            res.photos.forEach(p => {
                const slot = document.createElement("div");
                slot.className = "review-photo-slot";
                slot.dataset.id = p.id;
                slot.innerHTML = `
                    <input type="hidden" name="existing_photo_id[]" value="${p.id}">
                    <img src="${p.url}" alt="Facility Photo" class="review-photo-img">
                    <button type="button" class="review-dismiss-btn" title="Remove Photo" aria-label="Remove Photo">
                        <svg width="8" height="8" viewBox="3.4 3.4 6.8 6.8" fill="none" aria-hidden="true">
                            <path d="M4.35478 10.2004L3.40039 9.246L5.85453 6.79187L3.40039 4.35478L4.35478 3.40039L6.80891 5.85453L9.246 3.40039L10.2004 4.35478L7.74626 6.79187L10.2004 9.246L9.246 10.2004L6.80891 7.74626L4.35478 10.2004Z" fill="#4F576D"/>
                        </svg>
                    </button>
                `;
                firstPlaceholder ? grid.insertBefore(slot, firstPlaceholder) : grid?.appendChild(slot);
            });
            updatePhotoPlaceholders();
        }
        photoInput.value = "";
    });

    // -------------------------------------------------------------------------
    // 6. Add Product to Catalog Modal (Step 1 <-> Step 2 Wizard)
    // -------------------------------------------------------------------------
    const addProductModal       = document.getElementById("addProductModal");
    const addProductModalForm   = document.getElementById("addProductModalForm");
    const modalScopeId          = document.getElementById("modalScopeId");
    const modalBranchId         = document.getElementById("modalBranchId");
    const productModalStep1     = document.getElementById("productModalStep1");
    const productModalStep2     = document.getElementById("productModalStep2");
    const btnCloseProductModal  = document.getElementById("btnCloseProductModal");
    const btnCancelProductModal = document.getElementById("btnCancelProductModal");
    const btnGoToStep2          = document.getElementById("btnGoToStep2");
    const btnBackToStep1        = document.getElementById("btnBackToStep1");
    const productNameInput      = document.getElementById("productNameInput");
    const productNameField      = productNameInput?.closest(".product-modal__field") || null;
    const productScopeNotes     = document.getElementById("productScopeNotes");
    const productTestingChips   = document.getElementById("productTestingChips");
    const step2ProductTitle     = document.getElementById("step2ProductTitle");
    const step2ProductTags      = document.getElementById("step2ProductTags");
    const parametersTableBody   = document.getElementById("parametersTableBody");
    const btnAddParamRow        = document.getElementById("btnAddParamRow");
    const btnSaveCatalog        = document.getElementById("btnSaveCatalog");
    const saveCatalogBtnText    = document.getElementById("saveCatalogBtnText");
    const excelFileInput        = document.getElementById("excelFileInput");

    function createParamRow(name = "", method = "", unit = "", paramId = "") {
        const row = document.createElement("div");
        row.className = "product-modal__row product-modal__row--new";
        if (paramId) row.dataset.paramId = paramId;
        row.innerHTML = `
            <input type="hidden" name="param_id[]" value="${paramId}">
            <div class="product-modal__cell-param">
                <input type="text" required class="product-modal__row-input param-name-input" name="param_name[]" value="${escapeHtml(name)}" placeholder="Parameter Name...">
            </div>
            <div class="product-modal__cell-method">
                <input type="text" class="product-modal__row-input param-method-input" name="param_method[]" value="${escapeHtml(method)}" placeholder="Standard / Method...">
            </div>
            <div class="product-modal__cell-unit">
                <input type="text" class="product-modal__row-input param-unit-input" name="param_unit[]" value="${escapeHtml(unit)}" placeholder="Unit">
            </div>
            <div class="product-modal__cell-action">
                <button type="button" class="product-modal__del-btn" aria-label="Delete parameter">
                    <svg width="17" height="17" viewBox="0 0 17.3205 17.3205" fill="none" aria-hidden="true">
                        <path d="M6.78264 11.9078L8.65903 10.0314L10.5354 11.9078L11.5458 10.8974L9.66939 9.021L11.5458 7.14461L10.5354 6.13425L8.65903 8.01064L6.78264 6.13425L5.77228 7.14461L7.64867 9.021L5.77228 10.8974L6.78264 11.9078ZM5.05059 15.1553C4.65366 15.1553 4.31387 15.014 4.03121 14.7314C3.74854 14.4487 3.60721 14.1089 3.60721 13.712V4.33003H2.88553V2.88665H6.49396V2.16497H10.8241V2.88665H14.4325V4.33003H13.7108V13.712C13.7108 14.1089 13.5695 14.4487 13.2869 14.7314C13.0042 15.014 12.6644 15.1553 12.2675 15.1553H5.05059ZM12.2675 4.33003H5.05059V13.712H12.2675V4.33003Z" fill="#686868"/>
                    </svg>
                </button>
            </div>
        `;
        return row;
    }

    productTestingChips?.addEventListener("click", (e) => {
        const chip = e.target.closest(".product-modal__chip");
        if (chip) chip.classList.toggle("product-modal__chip--selected");
    });

    function openProductModal(scopeId = "", details = null, params = []) {
        if (!addProductModal) return;
        if (modalScopeId) modalScopeId.value = scopeId;
        if (excelFileInput) excelFileInput.value = "";
        const importLabel = document.querySelector('label[for="excelFileInput"] span');
        if (importLabel) importLabel.textContent = "Via Excel";

        const modalTitle = document.getElementById("productModalTitle");
        if (modalTitle) modalTitle.textContent = scopeId ? "Edit Product / Standard" : "Add Product to Catalog";

        if (scopeId && details) {
            if (productNameInput) productNameInput.value = details.name || details.title || "";
            if (productScopeNotes) productScopeNotes.value = details.notes || "";
            productNameField?.classList.remove("product-modal__field--error");

            const deptNames = new Set((details.departments || []).map(d => String(d).toLowerCase().trim()));
            productTestingChips?.querySelectorAll(".product-modal__chip").forEach(chip => {
                const type = (chip.getAttribute("data-type") || chip.textContent).toLowerCase().trim();
                chip.classList.toggle("product-modal__chip--selected", deptNames.has(type));
            });
        } else {
            if (productNameInput) productNameInput.value = "";
            if (productScopeNotes) productScopeNotes.value = "";
            productNameField?.classList.remove("product-modal__field--error");
            productTestingChips?.querySelectorAll(".product-modal__chip--selected").forEach(c => c.classList.remove("product-modal__chip--selected"));
        }

        if (parametersTableBody) {
            parametersTableBody.innerHTML = "";
            if (params?.length > 0) {
                params.forEach(p => parametersTableBody.appendChild(createParamRow(p.name, p.method, p.unit, p.id)));
            } else {
                parametersTableBody.appendChild(createParamRow());
            }
        }

        productModalStep1?.classList.remove("product-modal__step--hidden");
        productModalStep2?.classList.add("product-modal__step--hidden");
        addProductModal.classList.add("is-open");
        addProductModal.setAttribute("aria-hidden", "false");
        productNameInput?.focus();
    }

    function closeProductModal() {
        if (!addProductModal) return;
        addProductModal.classList.remove("is-open");
        addProductModal.setAttribute("aria-hidden", "true");
    }

    btnGoToStep2?.addEventListener("click", () => {
        const name = productNameInput?.value.trim();
        if (!name) {
            productNameField?.classList.add("product-modal__field--error");
            productNameInput?.focus();
            return;
        }
        productNameField?.classList.remove("product-modal__field--error");
        const selectedChips = Array.from(productTestingChips?.querySelectorAll(".product-modal__chip--selected") || [])
            .map(c => c.getAttribute("data-type") || c.textContent.trim());
        if (step2ProductTitle) step2ProductTitle.textContent = name;
        if (step2ProductTags) step2ProductTags.textContent = selectedChips.join(" & ") || "General";
        productModalStep1?.classList.add("product-modal__step--hidden");
        productModalStep2?.classList.remove("product-modal__step--hidden");
    });

    btnBackToStep1?.addEventListener("click", () => {
        productModalStep2?.classList.add("product-modal__step--hidden");
        productModalStep1?.classList.remove("product-modal__step--hidden");
    });

    productNameInput?.addEventListener("input", () => {
        if (productNameInput.value.trim()) productNameField?.classList.remove("product-modal__field--error");
    });

    document.getElementById("btnAddStandard")?.addEventListener("click", () => openProductModal());
    document.getElementById("btnAddProducts")?.addEventListener("click", () => openProductModal());
    btnCloseProductModal?.addEventListener("click", closeProductModal);
    btnCancelProductModal?.addEventListener("click", closeProductModal);
    addProductModal?.addEventListener("click", (e) => { if (e.target === addProductModal) closeProductModal(); });

    btnAddParamRow?.addEventListener("click", () => {
        if (!parametersTableBody) return;
        const newRow = createParamRow();
        parametersTableBody.appendChild(newRow);
        newRow.querySelector(".param-name-input")?.focus();
    });

    excelFileInput?.addEventListener("click", () => { excelFileInput.value = ""; });
    excelFileInput?.addEventListener("change", async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const importLabel = document.querySelector('label[for="excelFileInput"] span');
        const originalText = importLabel ? importLabel.textContent : "Via Excel";
        if (importLabel) importLabel.textContent = "Importing...";

        const formData = new FormData();
        formData.append("excel_file", file);

        try {
            const response = await fetch("/parse-scope-excel/", {
                method: "POST",
                body: formData,
                headers: { "X-CSRFToken": getCsrfToken(), "X-Requested-With": "XMLHttpRequest" }
            });
            const data = await response.json();
            if (data.status === "success" && data.rows?.length > 0 && parametersTableBody) {
                const existingRows = parametersTableBody.querySelectorAll(".product-modal__row");
                if (existingRows.length === 1 && !existingRows[0].querySelector(".param-name-input")?.value.trim()) {
                    parametersTableBody.innerHTML = "";
                }
                data.rows.forEach(r => {
                    parametersTableBody.appendChild(createParamRow(r.name || r.parameter_name || "", r.method || r.test_method || "", r.unit || ""));
                });
                if (importLabel) importLabel.textContent = `Imported (${data.rows.length})`;
            } else {
                alert(data.message || "No valid parameter rows found in file.");
                if (importLabel) importLabel.textContent = originalText;
            }
        } catch (err) {
            console.error("Excel import error:", err);
            alert("Failed to parse the file.");
            if (importLabel) importLabel.textContent = originalText;
        }
    });

    function renderScopeRowHtml(scopeData) {
        const paramsJson = JSON.stringify(scopeData.parameters || []);
        const detailsJson = JSON.stringify({
            id: String(scopeData.id),
            name: scopeData.is_number || "",
            title: scopeData.is_title || "",
            notes: scopeData.description || scopeData.scope_notes || "",
            departments: (scopeData.departments || []).map(d => typeof d === "string" ? d : d.name)
        });

        const isNum = scopeData.is_number || "Untitled Standard";
        const isTitle = scopeData.is_title && scopeData.is_title !== scopeData.is_number ? scopeData.is_title : "";
        let tagsHtml = "";

        (scopeData.departments || []).forEach(dept => {
            const displayName = typeof dept === "string" ? dept : dept.name || "";
            const dname = displayName.toLowerCase();
            let bg = "#F1F5F9", color = "#334155";
            if (dname.includes("chem")) { bg = "#ECFDF5"; color = "#047857"; }
            else if (dname.includes("mech")) { bg = "#F0F9FF"; color = "#0369A1"; }
            else if (dname.includes("metal")) { bg = "#FEF2F2"; color = "#B91C1C"; }
            tagsHtml += `<span class="ps-tag" style="display:inline-block;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:500;background-color:${bg};color:${color};">${escapeHtml(displayName)}</span>`;
        });
        if (!tagsHtml) {
            tagsHtml = `<span class="ps-tag" style="display:inline-block;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:500;background-color:#F1F5F9;color:#334155;">General</span>`;
        }

        return `
            <script type="application/json" class="scope-parameters-json">${paramsJson}</script>
            <script type="application/json" class="scope-details-json">${detailsJson}</script>
            <td style="text-align:center;padding:16px 8px 16px 16px;"><input type="checkbox" class="ps-checkbox"></td>
            <td style="padding:16px;">
                <div class="ps-standard-code" style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:4px;">${escapeHtml(isNum)}</div>
                ${isTitle ? `<div class="ps-standard-desc" style="font-size:12.5px;line-height:1.45;color:#64748B;">${escapeHtml(isTitle)}</div>` : ""}
            </td>
            <td style="padding:16px;"><div class="ps-tag-wrap" style="display:flex;flex-direction:column;gap:6px;align-items:flex-start;">${tagsHtml}</div></td>
            <td style="padding:16px;"><span class="ps-params-text" style="font-size:13px;font-weight:600;color:#334155;">${scopeData.param_count || 0} Params</span></td>
            <td style="padding:16px;text-align:right;">
                <button type="button" class="ps-btn-edit review-product-card__add-btn" data-scope-id="${scopeData.id}" aria-label="Edit Scope" style="background:transparent;border:none;cursor:pointer;padding:6px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0F3D39" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
            </td>
        `;
    }

    function updateCatalogUI(scopeData) {
        if (!scopeData) return;
        const emptyCard = document.getElementById("scopeEmptyCatalogCard");
        if (emptyCard) emptyCard.style.display = "none";

        let psTableBody = document.getElementById("psTableBody");
        if (!psTableBody) {
            const scopeCatalogForm = document.getElementById("scopeCatalogForm");
            if (scopeCatalogForm) {
                scopeCatalogForm.innerHTML = `
                    <div class="products-scope-main-wrapper" id="scopeCatalogContent">
                        <div class="products-scope-toolbar" style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;">
                            <div class="ps-search-box" style="position:relative;flex:1;">
                                <svg class="ps-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="position:absolute;left:14px;top:50%;transform:translateY(-50%);pointer-events:none;">
                                    <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                </svg>
                                <input type="text" id="psSearchInput" class="ps-search-input" placeholder="Search by standard code or title..." autocomplete="off" style="width:100%;height:44px;padding:0 16px 0 42px;background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;font-size:14px;color:#0F172A;box-sizing:border-box;outline:none;" />
                            </div>
                            <div class="ps-toolbar-actions" style="display:flex;align-items:center;gap:10px;">
                                <button type="button" class="btn-ps-add-standard" id="btnAddStandard" style="display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 20px;background-color:#F59E0B;color:#0F172A;border:none;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;white-space:nowrap;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                                    <span>Add Standard</span>
                                </button>
                            </div>
                        </div>
                        <div class="ps-table-wrapper" style="background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.02);">
                            <table class="ps-data-table" style="width:100%;border-collapse:collapse;text-align:left;">
                                <thead>
                                    <tr style="background-color:#F8FAFC;border-bottom:1px solid #E2E8F0;">
                                        <th style="width:40px;text-align:center;padding:14px 16px;"><input type="checkbox" id="selectAllStandards" class="ps-checkbox"></th>
                                        <th style="padding:14px 16px;font-size:11px;font-weight:700;color:#64748B;letter-spacing:0.04em;text-transform:uppercase;">STANDARD / SPECIFICATION</th>
                                        <th style="padding:14px 16px;font-size:11px;font-weight:700;color:#64748B;letter-spacing:0.04em;text-transform:uppercase;width:200px;">CATEGORY</th>
                                        <th style="padding:14px 16px;font-size:11px;font-weight:700;color:#64748B;letter-spacing:0.04em;text-transform:uppercase;width:120px;">PARAMETERS</th>
                                        <th style="width:50px;"></th>
                                    </tr>
                                </thead>
                                <tbody id="psTableBody"></tbody>
                            </table>
                        </div>
                    </div>
                `;
                psTableBody = document.getElementById("psTableBody");
                document.getElementById("btnAddStandard")?.addEventListener("click", () => openProductModal());
            }
        }

        const isNum = scopeData.is_number || "Untitled Standard";
        const isTitle = scopeData.is_title && scopeData.is_title !== scopeData.is_number ? scopeData.is_title : "";
        const searchStr = `${isNum.toLowerCase()} ${isTitle.toLowerCase()}`;
        const existingRow = psTableBody?.querySelector(`tr[data-scope-id="${scopeData.id}"]`);

        if (existingRow) {
            existingRow.setAttribute("data-search", searchStr);
            existingRow.innerHTML = renderScopeRowHtml(scopeData);
        } else if (psTableBody) {
            const newRow = document.createElement("tr");
            newRow.className = "ps-table-row";
            newRow.setAttribute("data-scope-id", scopeData.id);
            newRow.setAttribute("data-search", searchStr);
            newRow.style.cssText = "border-bottom: 1px solid #F1F5F9; vertical-align: top;";
            newRow.innerHTML = renderScopeRowHtml(scopeData);
            psTableBody.prepend(newRow);
        }
    }

    async function handleSaveCatalog(e) {
        if (e) e.preventDefault();
        const scopeId = modalScopeId?.value || "";
        const productName = productNameInput?.value.trim() || "";
        const scopeNotes = productScopeNotes?.value.trim() || "";

        if (!scopeId && !productName) {
            productModalStep2?.classList.add("product-modal__step--hidden");
            productModalStep1?.classList.remove("product-modal__step--hidden");
            productNameField?.classList.add("product-modal__field--error");
            productNameInput?.focus();
            return;
        }

        const paramNames = [], paramMethods = [], paramUnits = [];
        parametersTableBody?.querySelectorAll(".product-modal__row").forEach(row => {
            const name = row.querySelector(".param-name-input")?.value.trim() || "";
            if (name) {
                paramNames.push(name);
                paramMethods.push(row.querySelector(".param-method-input")?.value.trim() || "");
                paramUnits.push(row.querySelector(".param-unit-input")?.value.trim() || "");
            }
        });

        if (paramNames.length === 0) {
            const firstParamInput = parametersTableBody?.querySelector(".param-name-input");
            firstParamInput?.focus();
            alert("Please enter at least one parameter or import from Excel.");
            return;
        }

        const csrfToken = getCsrfToken();
        const formData = new FormData();
        formData.append("csrfmiddlewaretoken", csrfToken);
        if (modalBranchId?.value) formData.append("branch_id", modalBranchId.value);
        if (scopeId) formData.append("scope_id", scopeId);
        formData.append("product_name", productName);
        formData.append("scope_notes", scopeNotes);

        productTestingChips?.querySelectorAll(".product-modal__chip--selected").forEach(c => {
            formData.append("testing_types[]", c.getAttribute("data-type") || c.textContent.trim());
        });
        paramNames.forEach(n => formData.append("param_name[]", n));
        paramMethods.forEach(m => formData.append("param_method[]", m));
        paramUnits.forEach(u => formData.append("param_unit[]", u));

        if (btnSaveCatalog) btnSaveCatalog.disabled = true;
        if (saveCatalogBtnText) saveCatalogBtnText.textContent = "Saving...";

        try {
            const response = await fetch("/save-product-scope/", {
                method: "POST",
                body: formData,
                headers: { "X-CSRFToken": csrfToken, "X-Requested-With": "XMLHttpRequest" }
            });
            const result = await response.json();
            if (result.status === "success") {
                closeProductModal();
                updateCatalogUI(result.scope);
            } else {
                alert(result.message || "An error occurred while saving the product.");
            }
        } catch (err) {
            console.error("Save catalog error:", err);
            alert("Network error while saving catalog.");
        } finally {
            if (btnSaveCatalog) btnSaveCatalog.disabled = false;
            if (saveCatalogBtnText) saveCatalogBtnText.textContent = "Save Catalog";
        }
    }

    addProductModalForm?.addEventListener("submit", handleSaveCatalog);
    btnSaveCatalog?.addEventListener("click", handleSaveCatalog);

    // -------------------------------------------------------------------------
    // 7. Testing Packages Modal
    // -------------------------------------------------------------------------
    const addPackageModal      = document.getElementById("addPackageModal");
    const addPackageModalForm  = document.getElementById("addPackageModalForm");
    const modalPackageId       = document.getElementById("modalPackageId");
    const packageNameInput     = document.getElementById("packageNameInput");
    const packagePriceInput    = document.getElementById("packagePriceInput");
    const packageDiscountInput = document.getElementById("packageDiscountInput");
    const packageDescInput     = document.getElementById("packageDescInput");

    function openPackageModal(pkgId = "", name = "", price = "", discount = "", desc = "", selectedProductIds = []) {
        if (!addPackageModal) return;
        if (modalPackageId) modalPackageId.value = pkgId;
        if (packageNameInput) packageNameInput.value = name;
        if (packagePriceInput) packagePriceInput.value = price;
        if (packageDiscountInput) packageDiscountInput.value = discount;
        if (packageDescInput) packageDescInput.value = desc;

        document.querySelectorAll(".package-product-checkbox").forEach(chk => {
            chk.checked = selectedProductIds.includes(chk.value);
        });
        addPackageModal.classList.add("is-open");
        addPackageModal.setAttribute("aria-hidden", "false");
        packageNameInput?.focus();
    }

    function closePackageModal() {
        if (!addPackageModal) return;
        addPackageModal.classList.remove("is-open");
        addPackageModal.setAttribute("aria-hidden", "true");
    }

    document.getElementById("btnAddProductGroup")?.addEventListener("click", () => openPackageModal());
    document.getElementById("btnAddPackageGroup")?.addEventListener("click", () => openPackageModal());
    document.getElementById("btnEmptyAddPackages")?.addEventListener("click", () => openPackageModal());
    document.getElementById("btnClosePackageModal")?.addEventListener("click", closePackageModal);
    document.getElementById("btnCancelPackageModal")?.addEventListener("click", closePackageModal);
    addPackageModal?.addEventListener("click", (e) => { if (e.target === addPackageModal) closePackageModal(); });

    addPackageModalForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const csrfToken = getCsrfToken();
        const formData = new FormData(addPackageModalForm);
        formData.append("csrfmiddlewaretoken", csrfToken);

        try {
            const response = await fetch("/save-testing-package/", {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken }
            });
            const result = await response.json();
            if (result.status === "success") {
                closePackageModal();
                window.location.reload();
            } else {
                alert(result.message || "Failed to save package.");
            }
        } catch (err) {
            console.error("Save package error:", err);
            alert("Network error while saving package.");
        }
    });

    // -------------------------------------------------------------------------
    // 8. Custom Searchable Dropdowns (Country / State) & Lab Category Fields
    // -------------------------------------------------------------------------
    document.querySelectorAll(".review-custom-select:not(#labCategoryFieldCard)").forEach(cs => {
        const dropdown    = cs.querySelector(".review-custom-select__dropdown");
        const searchInput = cs.querySelector(".review-custom-select__search");
        const valueSpan   = cs.querySelector(".review-custom-select__value");
        const nativeSelect = cs.querySelector(".review-custom-select__native");

        cs.addEventListener("click", (e) => {
            if (e.target.closest(".review-custom-select__dropdown")) return;
            const isOpen = cs.classList.toggle("is-open");
            if (dropdown) dropdown.hidden = !isOpen;
            if (isOpen && searchInput) {
                searchInput.value = "";
                cs.querySelectorAll(".review-custom-select__option").forEach(o => { o.style.display = ""; });
                setTimeout(() => searchInput.focus(), 50);
            }
        });

        searchInput?.addEventListener("input", (e) => {
            const q = e.target.value.toLowerCase().trim();
            cs.querySelectorAll(".review-custom-select__option").forEach(opt => {
                opt.style.display = opt.textContent.toLowerCase().includes(q) ? "" : "none";
                opt.classList.remove("is-highlighted");
            });
        });

        dropdown?.addEventListener("click", (e) => {
            const opt = e.target.closest(".review-custom-select__option");
            if (!opt) return;
            if (valueSpan) {
                valueSpan.textContent = opt.textContent.trim();
                valueSpan.classList.remove("review-custom-select__value--placeholder");
            }
            if (nativeSelect) {
                nativeSelect.value = opt.dataset.value;
                nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
            }
            cs.classList.remove("is-open");
            if (dropdown) dropdown.hidden = true;
        });
    });

    const categorySelect = document.getElementById("facilityLabCategory");
    const categoryModal  = document.getElementById("categoryChangeModal");
    let pendingCatId = null;

    function bindDynamicCategoryInputEvents() {
        const dynamicInputs = document.querySelectorAll(".dynamic-category-input");
        if (!dynamicInputs.length) return;

        const saveCategoryData = async () => {
            const formData = new FormData();
            document.querySelectorAll(".dynamic-category-input").forEach(el => {
                const key = el.getAttribute("data-key");
                if (key) formData.append(`category_data[${key}]`, el.value);
            });
            await sendAutoSave("save_category_data", formData);
        };

        dynamicInputs.forEach(input => {
            const eventName = input.tagName.toLowerCase() === "select" ? "change" : "blur";
            input.removeEventListener(eventName, saveCategoryData);
            input.addEventListener(eventName, saveCategoryData);
        });
    }

    function renderDynamicCategoryFields(catName, fields, values) {
        const section    = document.getElementById("sectionCategorySpecific");
        const container  = document.getElementById("dynamicCategoryFieldsContainer");
        const titleSpan  = document.getElementById("dynCategoryTitle");
        const descSpan   = document.getElementById("dynCategoryDescName");
        const fieldList  = Array.isArray(fields) ? fields : [];

        if (!fieldList.length) {
            if (section) section.style.display = "none";
            if (container) container.innerHTML = "";
            return;
        }

        if (titleSpan) titleSpan.textContent = catName || "";
        if (descSpan) descSpan.textContent = catName || "";
        if (container) container.innerHTML = "";

        fieldList.forEach(field => {
            const val = values?.[field.key] ?? "";
            const requiredStar = field.required ? '<span style="color:red;">*</span>' : "";
            const card = document.createElement("div");
            card.className = "review-field-card";

            let inputHtml = "";
            if (field.type === "boolean") {
                const isTrue = String(val) === "true";
                inputHtml = `<select id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}"><option value="true" ${isTrue ? "selected" : ""}>Yes</option><option value="false" ${!isTrue ? "selected" : ""}>No</option></select>`;
            } else if (field.type === "textarea") {
                inputHtml = `<textarea id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}" rows="3" placeholder="${escapeHtml(field.placeholder || "")}">${escapeHtml(val)}</textarea>`;
            } else {
                const typeAttr = field.type === "number" ? 'type="number" step="any"' : 'type="text"';
                inputHtml = `<input ${typeAttr} id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}" value="${escapeHtml(val)}" placeholder="${escapeHtml(field.placeholder || "")}">`;
            }

            card.innerHTML = `<label for="dyn_${field.key}" class="review-field-label review-field-label--slate">${escapeHtml(field.label)} ${requiredStar}</label>${inputHtml}`;
            container?.appendChild(card);
        });

        if (section) section.style.display = "block";
        bindDynamicCategoryInputEvents();
    }

    async function triggerCategorySave() {
        const formData = new FormData();
        const generalContainer = document.getElementById("tab-general") || document;
        generalContainer.querySelectorAll("input, select, textarea").forEach(el => {
            if (el.name && !el.disabled) formData.append(el.name, el.value);
        });

        if (categorySelect) {
            const selectedCatVal = categorySelect.value;
            formData.set("lab_category", selectedCatVal);
            formData.set("lab_category_id", selectedCatVal);
            formData.set("facility_lab_category", selectedCatVal);
        }

        const res = await sendAutoSave("save_general", formData);
        if (res && (res.status === "success" || res.status === 200 || res.success)) {
            const updatedCatId = res.category_id || categorySelect?.value || "";
            if (categorySelect) {
                categorySelect.value = updatedCatId;
                categorySelect.setAttribute("data-current-category-id", updatedCatId);
            }
            renderDynamicCategoryFields(
                res.category_name || categorySelect?.options[categorySelect.selectedIndex]?.text || "",
                res.fields || res.category_fields || res.schema || [],
                res.category_data || res.values || {}
            );
        }
    }

    categorySelect?.addEventListener("change", async () => {
        const newCatId = categorySelect.value;
        const currentCatId = categorySelect.getAttribute("data-current-category-id");
        if (!newCatId) return;

        if (currentCatId && String(currentCatId).trim() !== "" && String(currentCatId) !== String(newCatId)) {
            pendingCatId = newCatId;
            categoryModal?.classList.add("is-open");
            categoryModal?.setAttribute("aria-hidden", "false");
        } else {
            await triggerCategorySave();
        }
    });

    document.getElementById("btnCancelCategoryChange")?.addEventListener("click", () => {
        categoryModal?.classList.remove("is-open");
        categoryModal?.setAttribute("aria-hidden", "true");
        if (categorySelect) categorySelect.value = categorySelect.getAttribute("data-current-category-id") || "";
        pendingCatId = null;
    });

    document.getElementById("btnConfirmCategoryChange")?.addEventListener("click", async () => {
        categoryModal?.classList.remove("is-open");
        categoryModal?.setAttribute("aria-hidden", "true");
        if (pendingCatId && categorySelect) {
            categorySelect.value = pendingCatId;
            await triggerCategorySave();
        }
    });

    bindDynamicCategoryInputEvents();

    // -------------------------------------------------------------------------
    // 9. Global Delegated Click, Input & Keyboard Handlers
    // -------------------------------------------------------------------------
    document.addEventListener("input", (e) => {
        if (e.target?.id === "psSearchInput") {
            const query = e.target.value.toLowerCase().trim();
            document.querySelectorAll("#psTableBody tr").forEach(row => {
                const match = (row.getAttribute("data-search") || "").toLowerCase().includes(query) ||
                              row.textContent.toLowerCase().includes(query);
                row.style.display = match ? "" : "none";
            });
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            if (socialDropdown && !socialDropdown.hasAttribute("hidden")) closeSocialDropdown();
            if (addProductModal?.classList.contains("is-open")) closeProductModal();
            if (addPackageModal?.classList.contains("is-open")) closePackageModal();
        } else if (e.target.matches(".review-accred-date-input") && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            try { e.target.showPicker(); } catch (err) { e.target.click(); }
        }
    });

    document.addEventListener("click", async (e) => {
        // A. Outside click closes social & custom select dropdowns
        if (socialDropdown && !socialDropdown.hasAttribute("hidden") && !socialDropdown.contains(e.target) && !socialCard?.contains(e.target)) {
            closeSocialDropdown();
        }
        if (!e.target.closest(".review-custom-select")) {
            document.querySelectorAll(".review-custom-select").forEach(cs => {
                cs.classList.remove("is-open");
                const dd = cs.querySelector(".review-custom-select__dropdown");
                if (dd) dd.hidden = true;
            });
        }

        // B. Tag Pill Toggle (Disciplines, Testing Types, Categories, Subcategories)
        const pill = e.target.closest(".review-tag-pill");
        if (pill) {
            let groupKey = null;
            if (pill.dataset.disciplineId) groupKey = "discipline";
            else if (pill.dataset.departmentId) groupKey = "department";
            else if (pill.dataset.subcategoryId) groupKey = "subcategory";
            else if (pill.dataset.categoryId) groupKey = "category";

            if (groupKey) {
                const group = tagGroups[groupKey];
                const id = String(pill.dataset[group.idAttr] || "").trim();
                const isCurrentlySelected = Boolean(pill.closest(".review-tag-box__selected"));

                if (isCurrentlySelected) {
                    pill.remove();
                    const suggestionChip = group.suggestionsWrap?.querySelector(`[${group.dataAttrName}="${id}"]`);
                    if (suggestionChip) setPillVisualState(suggestionChip, false);
                } else {
                    const clone = pill.cloneNode(true);
                    showChip(clone, true);
                    setPillVisualState(clone, true);
                    group.selectedWrap?.appendChild(clone);
                    if (group.input) group.input.value = "";
                }

                renderTagSuggestions(groupKey);
                await saveTagGroup(groupKey);

                if (groupKey === "category") {
                    const validCatIds = getSelectedCategoryIds();
                    const subGroup = tagGroups.subcategory;
                    let pruned = false;
                    subGroup.selectedWrap?.querySelectorAll(".review-tag-pill").forEach(subChip => {
                        if (!validCatIds.has(String(subChip.dataset.categoryId || "").trim())) {
                            subChip.remove();
                            pruned = true;
                        }
                    });
                    renderTagSuggestions("subcategory");
                    if (pruned) await saveTagGroup("subcategory");
                }
                return;
            }
        }

        // C. Accreditation field focus / date picker
        const accredField = e.target.closest(".review-accred-field");
        if (accredField) {
            if (accredField.classList.contains("review-accred-field--validity")) {
                const dateInput = accredField.querySelector(".review-accred-date-input");
                if (dateInput) { try { dateInput.showPicker(); } catch (err) { dateInput.focus(); } }
            } else {
                const input = accredField.querySelector(".review-accred-input");
                if (input && document.activeElement !== input) input.focus();
            }
            return;
        }

        // D. Delete Parameter Row in Product Modal
        const delParamBtn = e.target.closest(".product-modal__del-btn");
        if (delParamBtn) {
            const row = delParamBtn.closest(".product-modal__row");
            if (row && parametersTableBody) {
                if (row.dataset.paramId) {
                    const fd = new FormData();
                    fd.append("param_id", row.dataset.paramId);
                    await sendAutoSave("delete_parameter", fd);
                }
                row.remove();
                if (!parametersTableBody.querySelectorAll(".product-modal__row").length) {
                    parametersTableBody.appendChild(createParamRow());
                }
            }
            return;
        }

        // E. Edit Package Card
        const editPkgBtn = e.target.closest(".review-edit-package-btn");
        if (editPkgBtn) {
            const card = editPkgBtn.closest(".review-product-card");
            const pkgId = card?.getAttribute("data-package-id") || "";
            const title = card?.querySelector(".review-product-card__title")?.textContent.trim() || "";
            const priceText = card?.querySelector(".review-package-price-text")?.textContent || "";
            const price = priceText.match(/₹([\d.]+)/)?.[1] || "";
            const discount = priceText.match(/\(([\d.]+)% Off\)/)?.[1] || "";
            let productIds = [], description = "";

            const jsonScript = card?.querySelector(".package-products-json");
            if (jsonScript) {
                try {
                    const data = JSON.parse(jsonScript.textContent.trim());
                    description = data.description || "";
                    productIds = (data.products || []).map(p => String(p.id));
                } catch (err) { console.error("Error parsing package JSON:", err); }
            }
            openPackageModal(pkgId, title, price, discount, description, productIds);
            return;
        }

        // F. Edit Product / Standard Scope
        const editScopeBtn = e.target.closest(".ps-btn-edit, .review-product-card__add-btn");
        if (editScopeBtn) {
            const row = editScopeBtn.closest(".ps-table-row, .review-product-card");
            const scopeId = editScopeBtn.getAttribute("data-scope-id") || row?.getAttribute("data-scope-id") || "";
            let details = null, parameters = [];

            const detailsScript = row?.querySelector(".scope-details-json");
            if (detailsScript) {
                try { details = JSON.parse(detailsScript.textContent.trim()); } catch (err) {}
            }
            if (!details && row) {
                const code = row.querySelector(".ps-standard-code, .review-product-card__title")?.textContent.trim() || "";
                const desc = row.querySelector(".ps-standard-desc")?.textContent.trim() || "";
                const tags = Array.from(row.querySelectorAll(".ps-tag, .review-product-tag span")).map(t => t.textContent.trim());
                details = { id: scopeId, name: code, title: code, notes: desc, departments: tags };
            }
            const paramsScript = row?.querySelector(".scope-parameters-json");
            if (paramsScript) {
                try { parameters = JSON.parse(paramsScript.textContent.trim()); } catch (err) {}
            }
            openProductModal(scopeId, details, parameters);
            return;
        }

        // G. Dismiss / Delete Cards (Service, Accreditation, Photo, Package, Product Scope)
        const dismissBtn = e.target.closest(".review-dismiss-btn");
        if (dismissBtn) {
            const serviceCard = dismissBtn.closest(".review-service-card");
            if (serviceCard) {
                if (serviceCard.dataset.id) {
                    const fd = new FormData();
                    fd.append("service_id", serviceCard.dataset.id);
                    await sendAutoSave("delete_service", fd);
                }
                serviceCard.remove();
                return;
            }

            const accredRow = dismissBtn.closest(".review-accreditation-row");
            if (accredRow) {
                if (accredRow.dataset.id) {
                    const fd = new FormData();
                    fd.append("accred_id", accredRow.dataset.id);
                    await sendAutoSave("delete_accreditation", fd);
                }
                accredRow.remove();
                return;
            }

            const photoSlot = dismissBtn.closest(".review-photo-slot");
            if (photoSlot) {
                if (photoSlot.dataset.id) {
                    const fd = new FormData();
                    fd.append("photo_id", photoSlot.dataset.id);
                    await sendAutoSave("delete_photo", fd);
                }
                photoSlot.remove();
                updatePhotoPlaceholders();
                return;
            }

            const productCard = dismissBtn.closest(".review-product-card");
            if (productCard) {
                if (productCard.hasAttribute("data-package-id")) {
                    if (!confirm("Are you sure you want to delete this package?")) return;
                    const fd = new FormData();
                    fd.append("package_id", productCard.getAttribute("data-package-id"));
                    const res = await sendAutoSave("delete_package", fd);
                    if (res?.status === "success") productCard.remove();
                    else alert(res?.message || "Failed to delete package.");
                } else {
                    if (productCard.dataset.scopeId) {
                        const fd = new FormData();
                        fd.append("scope_id", productCard.dataset.scopeId);
                        await sendAutoSave("delete_scope", fd);
                    }
                    productCard.remove();
                    const grid = document.getElementById("productsGrid");
                    if (grid && !grid.querySelectorAll(".review-product-card").length) {
                        const emptyTabMsg = document.getElementById("scopeTabEmptyMessage");
                        if (emptyTabMsg) emptyTabMsg.style.display = "block";
                    }
                }
                return;
            }
        }

        // H. Submit Profile for Approval
        const submitBtn = e.target.closest("#btnSubmitApproval");
        if (submitBtn) {
            if (submitBtn.disabled || isUnderReview()) {
                showUnderReviewAlert();
                return;
            }
            if (!confirm("Are you sure you want to submit your profile for approval?")) return;
            const res = await sendAutoSave("submit_for_approval", new FormData());
            if (res?.status === "success") {
                submitBtn.disabled = true;
                submitBtn.dataset.labStatus = "reviewed";
                submitBtn.textContent = "Submitted For Approval";
                submitBtn.style.opacity = "0.65";
                submitBtn.style.cursor = "not-allowed";
                alert(res.message || "Profile submitted for approval successfully!");
                window.location.href = "/lab-review-detail/";
            } else {
                alert(res?.message || "Failed to submit profile. Please try again.");
            }
        }
    });
});