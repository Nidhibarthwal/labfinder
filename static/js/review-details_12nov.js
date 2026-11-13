document.addEventListener("DOMContentLoaded", () => {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";

    // to auto update the form
    async function sendAutoSave(action, formData) {
        formData.append("action", action);
        formData.append("csrfmiddlewaretoken", csrfToken);
        try {
            const response = await window.fetch(window.location.href, {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });
            return await response.json();
        } catch (err) {
            console.error("Auto-save error:", err);
        }
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
                    const elementTop = targetEl.getBoundingClientRect().top + window.scrollY;
                    const offsetPosition = Math.max(0, elementTop - headerHeight - 24);

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
            if (el && step) {
                const top = el.offsetTop;
                const height = el.offsetHeight;
                if (scrollPos >= top && scrollPos < top + height) {
                    stepLinks.forEach((s) => s.classList.remove("review-step--active"));
                    step.classList.add("review-step--active");
                }
            }
        });
    }, { passive: true });

    // -------------------------------------------------------------------------
    // 2. Dropdown Menus (Disciplines & Testing Types)
    // -------------------------------------------------------------------------
    const dropdownControllers = [
        {
            btn: document.getElementById("btnSearchDisciplines"),
            dropdown: document.getElementById("disciplinesDropdown"),
            closeBtn: document.getElementById("btnCloseDisciplines"),
            input: document.getElementById("disciplinesSearchInput"),
            chips: document.getElementById("disciplinesChips")
        },
        {
            btn: document.getElementById("btnAddType"),
            dropdown: document.getElementById("typesDropdown"),
            closeBtn: document.getElementById("btnCloseTypes"),
            input: document.getElementById("typesSearchInput"),
            chips: document.getElementById("typesChips")
        },
        {
            btn: document.getElementById("btnSearchCategories"),
            dropdown: document.getElementById("categoriesDropdown"),
            closeBtn: document.getElementById("btnCloseCategories"),
            input: document.getElementById("categoriesSearchInput"),
            chips: document.getElementById("categoriesChips")
        },
        {
            btn: document.getElementById("btnAddSubcategory"),
            dropdown: document.getElementById("subcategoriesDropdown"),
            closeBtn: document.getElementById("btnCloseSubcategories"),
            input: document.getElementById("subcategoriesSearchInput"),
            chips: document.getElementById("subcategoriesChips")
        }
    ];

    function closeReviewDropdown(ctrl) {
        if (!ctrl || !ctrl.dropdown || ctrl.dropdown.hasAttribute("hidden")) return;
        const section = ctrl.dropdown.closest(".review-section");
        if (section) section.classList.remove("review-section--elevated");
        ctrl.dropdown.setAttribute("hidden", "");
        if (ctrl.btn) ctrl.btn.setAttribute("aria-expanded", "false");
    }

    function openReviewDropdown(ctrl) {
        if (!ctrl || !ctrl.dropdown) return;
        dropdownControllers.forEach(c => { if (c !== ctrl) closeReviewDropdown(c); });
        closeSocialDropdown();

        const section = ctrl.dropdown.closest(".review-section");
        if (section) section.classList.add("review-section--elevated");
        ctrl.dropdown.removeAttribute("hidden");
        if (ctrl.btn) ctrl.btn.setAttribute("aria-expanded", "true");
        if (ctrl.input) ctrl.input.focus();
    }

    dropdownControllers.forEach(ctrl => {
        if (ctrl.btn && ctrl.dropdown) {
            ctrl.btn.addEventListener("click", (e) => {
                e.stopPropagation();
                ctrl.dropdown.hasAttribute("hidden") ? openReviewDropdown(ctrl) : closeReviewDropdown(ctrl);
            });
        }
        if (ctrl.closeBtn) {
            ctrl.closeBtn.addEventListener("click", () => closeReviewDropdown(ctrl));
        }
        if (ctrl.input && ctrl.chips) {
            ctrl.input.addEventListener("input", () => {
                const query = ctrl.input.value.trim().toLowerCase();
                ctrl.chips.querySelectorAll(".review-tag-pill").forEach(chip => {
                    const text = (chip.getAttribute("data-tag") || chip.textContent).toLowerCase();
                    chip.style.display = text.includes(query) ? "" : "none";
                });
            });
        }
    });

    function closeDisciplinesDropdown() {
        closeReviewDropdown(dropdownControllers[0]);
    }

    function closeTypesDropdown() {
        closeReviewDropdown(dropdownControllers[1]);
    }

    document.addEventListener("click", (e) => {
        dropdownControllers.forEach(ctrl => {
            if (ctrl.dropdown && !ctrl.dropdown.hasAttribute("hidden")) {
                if (!ctrl.dropdown.contains(e.target) && !ctrl.btn.contains(e.target)) {
                    closeReviewDropdown(ctrl);
                }
            }
        });
        if (socialDropdown && !socialDropdown.hasAttribute("hidden")) {
            if (!socialDropdown.contains(e.target) && !socialCard.contains(e.target)) {
                closeSocialDropdown();
            }
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            dropdownControllers.forEach(ctrl => {
                if (ctrl.dropdown && !ctrl.dropdown.hasAttribute("hidden")) {
                    closeReviewDropdown(ctrl);
                    if (ctrl.btn) ctrl.btn.focus();
                }
            });
            if (socialDropdown && !socialDropdown.hasAttribute("hidden")) {
                closeSocialDropdown();
                if (socialCard) socialCard.focus();
            }
            if (addProductModal && addProductModal.classList.contains("is-open")) {
                closeProductModal();
            }
        }
    });

    // -------------------------------------------------------------------------
    // 3. Social Media Links Dropdown
    // -------------------------------------------------------------------------
    const socialHeader   = document.getElementById("socialMediaHeader");
    const socialCard     = document.getElementById("socialMediaCard");
    const socialDropdown = document.getElementById("socialMediaDropdown");

    function openSocialDropdown() {
        if (!socialDropdown) return;
        closeDisciplinesDropdown();
        closeTypesDropdown();
        const section = socialDropdown.closest(".review-section");
        if (section) section.classList.add("review-section--elevated");
        socialDropdown.removeAttribute("hidden");
        if (socialCard) {
            socialCard.setAttribute("aria-expanded", "true");
            socialCard.classList.add("is-open");
        }
        if (socialHeader) socialHeader.setAttribute("aria-expanded", "true");
    }

    function closeSocialDropdown() {
        if (!socialDropdown) return;
        const section = socialDropdown.closest(".review-section");
        if (section) section.classList.remove("review-section--elevated");
        socialDropdown.setAttribute("hidden", "");
        if (socialCard) {
            socialCard.setAttribute("aria-expanded", "false");
            socialCard.classList.remove("is-open");
        }
        if (socialHeader) socialHeader.setAttribute("aria-expanded", "false");
    }

    if (socialCard && socialDropdown) {
        socialCard.addEventListener("click", (e) => {
            if (socialDropdown.contains(e.target) || e.target.closest(".review-social-btn")) return;
            const isOpen = !socialDropdown.hasAttribute("hidden");
            isOpen ? closeSocialDropdown() : openSocialDropdown();
        });
    }

    // -------------------------------------------------------------------------
    // 4. Accreditations: Input & Date Picker Helpers
    // -------------------------------------------------------------------------
    document.addEventListener("click", (e) => {
        const field = e.target.closest(".review-accred-field");
        if (field && !field.classList.contains("review-accred-field--validity")) {
            const input = field.querySelector(".review-accred-input");
            if (input && document.activeElement !== input) input.focus();
        }
    });

    document.addEventListener("click", (e) => {
        const validityField = e.target.closest(".review-accred-field--validity");
        if (validityField) {
            const dateInput = validityField.querySelector(".review-accred-date-input");
            if (dateInput) {
                try { dateInput.showPicker(); } catch (err) { dateInput.focus(); }
            }
        }
    });

    document.addEventListener("change", async (e) => {
        if (e.target.matches(".review-accred-date-input")) {
            const val = e.target.value;
            const validityField = e.target.closest(".review-accred-field--validity");
            const textSpan = validityField?.querySelector(".review-accred-field-text");
            if (textSpan) {
                if (val) {
                    const [y, m, d] = val.split("-");
                    textSpan.textContent = `${d}/${m}/${y}`;
                } else {
                    textSpan.textContent = "DD/MM/YYYY";
                }
            }
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        }

        if (e.target.matches(".review-accred-logo-input") && e.target.files?.[0]) {
            const img = e.target.closest(".review-accred-logo-box")?.querySelector("img");
            if (img) img.src = URL.createObjectURL(e.target.files[0]);
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        }
    });

    // Allow keyboard users (Enter / Space) to trigger the date picker
    document.addEventListener("keydown", (e) => {
        if (e.target.matches(".review-accred-date-input") && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            try { e.target.showPicker(); } catch (err) { e.target.click(); }
        }
    });

    // -------------------------------------------------------------------------
    // 5. Add Product to Catalog Modal: Step 1 <-> Step 2 Wizard
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
    const productNameField      = productNameInput ? productNameInput.closest(".product-modal__field") : null;
    const productScopeNotes     = document.getElementById("productScopeNotes");
    const productTestingChips   = document.getElementById("productTestingChips");
    const step2ProductTitle     = document.getElementById("step2ProductTitle");
    const step2ProductTags      = document.getElementById("step2ProductTags");
    const btnAddStandard        = document.getElementById("btnAddStandard");
    const btnAddProductGroup    = document.getElementById("btnAddProductGroup");
    const btnAddProducts        = document.getElementById("btnAddProducts");
    const parametersTableBody   = document.getElementById("parametersTableBody");
    const btnAddParamRow        = document.getElementById("btnAddParamRow");
    const btnSaveCatalog        = document.getElementById("btnSaveCatalog");
    const saveCatalogBtnText    = document.getElementById("saveCatalogBtnText");
    const excelFileInput        = document.getElementById("excelFileInput");

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

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

    // Type of Testing Chip Multi-select Handler
    productTestingChips?.addEventListener("click", (e) => {
        const chip = e.target.closest(".product-modal__chip");
        if (!chip) return;
        chip.classList.toggle("product-modal__chip--selected");
    });

    function openProductModal(scopeId = "", details = null, params = []) {
        if (!addProductModal) return;
        if (modalScopeId) modalScopeId.value = scopeId;
        if (excelFileInput) excelFileInput.value = "";
        const importLabel = document.querySelector('label[for="excelFileInput"] span');
        if (importLabel) importLabel.textContent = "Via Excel";

        const modalTitle = document.getElementById("productModalTitle");
        if (modalTitle) {
            modalTitle.textContent = scopeId ? "Edit Product / Standard" : "Add Product to Catalog";
        }

        if (scopeId && details) {
            if (productNameInput) productNameInput.value = details.name || details.title || "";
            if (productScopeNotes) productScopeNotes.value = details.notes || "";
            if (productNameField) productNameField.classList.remove("product-modal__field--error");

            // Sync testing type chips
            const deptNames = new Set((details.departments || []).map(d => String(d).toLowerCase().trim()));
            productTestingChips?.querySelectorAll(".product-modal__chip").forEach(chip => {
                const type = (chip.getAttribute("data-type") || chip.textContent).toLowerCase().trim();
                if (deptNames.has(type)) {
                    chip.classList.add("product-modal__chip--selected");
                } else {
                    chip.classList.remove("product-modal__chip--selected");
                }
            });
        } else {
            if (productNameInput) productNameInput.value = "";
            if (productScopeNotes) productScopeNotes.value = "";
            if (productNameField) productNameField.classList.remove("product-modal__field--error");
            productTestingChips?.querySelectorAll(".product-modal__chip--selected").forEach(c => {
                c.classList.remove("product-modal__chip--selected");
            });
        }

        // Populate parameters table: 1 blank row by default if empty
        if (parametersTableBody) {
            parametersTableBody.innerHTML = "";
            if (params && params.length > 0) {
                params.forEach(p => {
                    parametersTableBody.appendChild(createParamRow(p.name, p.method, p.unit, p.id));
                });
            } else {
                parametersTableBody.appendChild(createParamRow());
            }
        }

        // Always open on Step 1 so scope details are visible
        if (productModalStep1) productModalStep1.classList.remove("product-modal__step--hidden");
        if (productModalStep2) productModalStep2.classList.add("product-modal__step--hidden");
        addProductModal.classList.add("is-open");
        addProductModal.setAttribute("aria-hidden", "false");
        if (productNameInput) productNameInput.focus();
    }

    function closeProductModal() {
        if (!addProductModal) return;
        addProductModal.classList.remove("is-open");
        addProductModal.setAttribute("aria-hidden", "true");
    }

    function goToStep2(title, tags) {
        if (step2ProductTitle && title) step2ProductTitle.textContent = title;
        if (step2ProductTags && tags) step2ProductTags.textContent = tags;
        if (productModalStep1) productModalStep1.classList.add("product-modal__step--hidden");
        if (productModalStep2) productModalStep2.classList.remove("product-modal__step--hidden");
        if (addProductModal) { addProductModal.classList.add("is-open"); addProductModal.setAttribute("aria-hidden", "false"); }
    }

    btnGoToStep2?.addEventListener("click", () => {
        const name = productNameInput?.value.trim();
        if (!name) {
            if (productNameField) productNameField.classList.add("product-modal__field--error");
            if (productNameInput) productNameInput.focus();
            return;
        }
        if (productNameField) productNameField.classList.remove("product-modal__field--error");
        const selectedChips = Array.from(productTestingChips?.querySelectorAll(".product-modal__chip--selected") || []).map(c => c.getAttribute("data-type") || c.textContent.trim());
        goToStep2(name, selectedChips.join(" & ") || "General");
    });

    // Clear error class when typing in product name
    productNameInput?.addEventListener("input", () => {
        if (productNameInput.value.trim() && productNameField) {
            productNameField.classList.remove("product-modal__field--error");
        }
    });

    // Edit Scope Details & Parameters on edit button click
    document.addEventListener("click", (e) => {
        const editBtn = e.target.closest(".ps-btn-edit, .review-product-card__add-btn");
        if (!editBtn) return;
        if (editBtn.classList.contains("review-edit-package-btn")) return;

        const row = editBtn.closest(".ps-table-row, .review-product-card");
        const scopeId = editBtn.getAttribute("data-scope-id") || row?.getAttribute("data-scope-id") || "";

        let details = null;
        const detailsScript = row?.querySelector(".scope-details-json");
        if (detailsScript) {
            try {
                details = JSON.parse(detailsScript.textContent.trim());
            } catch (err) {
                console.error("Error parsing details json:", err);
            }
        }

        if (!details && row) {
            const code = row.querySelector(".ps-standard-code, .review-product-card__title")?.textContent.trim() || "";
            const desc = row.querySelector(".ps-standard-desc")?.textContent.trim() || "";
            const tags = Array.from(row.querySelectorAll(".ps-tag, .review-product-tag span")).map(t => t.textContent.trim());
            details = {
                id: scopeId,
                name: code,
                title: code,
                notes: desc,
                departments: tags
            };
        }

        let parameters = [];
        const paramsScript = row?.querySelector(".scope-parameters-json");
        if (paramsScript) {
            try {
                parameters = JSON.parse(paramsScript.textContent.trim());
            } catch (err) {
                console.error("Error parsing parameters json:", err);
            }
        }

        openProductModal(scopeId, details, parameters);
    });

    // Reset file input on click so re-selecting same file triggers change
    excelFileInput?.addEventListener("click", () => {
        excelFileInput.value = "";
    });

    // Excel file selection & clean mapping (Name -> Method -> Unit)
    excelFileInput?.addEventListener("change", async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const importLabel = document.querySelector('label[for="excelFileInput"] span');
        const originalText = importLabel ? importLabel.textContent : "Via Excel";
        if (importLabel) importLabel.textContent = "Importing...";

        const formData = new FormData();
        formData.append("excel_file", file);
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";

        try {
            const response = await fetch("/parse-scope-excel/", {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            const data = await response.json();
            if (data.status === "success" && data.rows && data.rows.length > 0) {
                if (parametersTableBody) {
                    const existingRows = parametersTableBody.querySelectorAll(".product-modal__row");
                    const hasOnlyEmptyRow = existingRows.length === 1 &&
                        !existingRows[0].querySelector(".param-name-input")?.value.trim();
                    if (hasOnlyEmptyRow) {
                        parametersTableBody.innerHTML = "";
                    }

                    // Map cleanly into distinct columns: Name, Method/Standard, Unit
                    data.rows.forEach(r => {
                        parametersTableBody.appendChild(createParamRow(
                            r.name || r.parameter_name || "", 
                            r.method || r.test_method || "", 
                            r.unit || ""
                        ));
                    });
                }
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

    // Step 2 -> Step 1: Return to Step 1 preserving entered values
    if (btnBackToStep1) {
        btnBackToStep1.addEventListener("click", () => {
            if (productModalStep2) productModalStep2.classList.add("product-modal__step--hidden");
            if (productModalStep1) productModalStep1.classList.remove("product-modal__step--hidden");
        });
    }

    // Add New Parameter Row (1 row added)
    btnAddParamRow?.addEventListener("click", () => {
        if (!parametersTableBody) return;
        const newRow = createParamRow();
        parametersTableBody.appendChild(newRow);
        newRow.querySelector(".param-name-input")?.focus();
    });

    // Delete Parameter Row
    document.addEventListener("click", async (e) => {
        const delBtn = e.target.closest(".product-modal__del-btn");
        if (!delBtn) return;
        const row = delBtn.closest(".product-modal__row");
        if (row && parametersTableBody) {
            const paramId = row.dataset.paramId;
            if (paramId) {
                const formData = new FormData();
                formData.append("param_id", paramId);
                await sendAutoSave("delete_parameter", formData);
            }
            row.remove();
            if (parametersTableBody.querySelectorAll(".product-modal__row").length === 0) {
                parametersTableBody.appendChild(createParamRow());
            }
        }
    });

    // Save Catalog (BranchItem & TestingScopeFacility)
    async function handleSaveCatalog(e) {
        if (e) e.preventDefault();

        const scopeId = modalScopeId?.value || "";
        const productName = productNameInput ? productNameInput.value.trim() : "";
        const scopeNotes = productScopeNotes ? productScopeNotes.value.trim() : "";

        // If new scope and product name is missing, prompt user on Step 1
        if (!scopeId && !productName) {
            if (productModalStep2) productModalStep2.classList.add("product-modal__step--hidden");
            if (productModalStep1) productModalStep1.classList.remove("product-modal__step--hidden");
            if (productNameField) productNameField.classList.add("product-modal__field--error");
            if (productNameInput) productNameInput.focus();
            return;
        }

        // Collect parameter rows
        const rows = parametersTableBody ? parametersTableBody.querySelectorAll(".product-modal__row") : [];
        const paramNames = [];
        const paramMethods = [];
        const paramUnits = [];

        rows.forEach(row => {
            const name = row.querySelector(".param-name-input")?.value.trim() || "";
            const method = row.querySelector(".param-method-input")?.value.trim() || "";
            const unit = row.querySelector(".param-unit-input")?.value.trim() || "";
            if (name) {
                paramNames.push(name);
                paramMethods.push(method);
                paramUnits.push(unit);
            }
        });

        if (paramNames.length === 0) {
            const firstParamInput = parametersTableBody?.querySelector(".param-name-input");
            if (firstParamInput) {
                firstParamInput.focus();
                firstParamInput.classList.add("product-modal__input--error");
                setTimeout(() => firstParamInput.classList.remove("product-modal__input--error"), 2000);
            }
            alert("Please enter at least one parameter or import from Excel.");
            return;
        }

        const selectedChips = Array.from(productTestingChips?.querySelectorAll(".product-modal__chip--selected") || [])
            .map(c => c.getAttribute("data-type") || c.textContent.trim());

        const formData = new FormData();
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";
        formData.append("csrfmiddlewaretoken", csrfToken);

        const branchId = modalBranchId?.value || "";
        if (branchId) formData.append("branch_id", branchId);
        if (scopeId) formData.append("scope_id", scopeId);
        formData.append("product_name", productName);
        formData.append("scope_notes", scopeNotes);

        selectedChips.forEach(chip => formData.append("testing_types[]", chip));
        paramNames.forEach(name => formData.append("param_name[]", name));
        paramMethods.forEach(method => formData.append("param_method[]", method));
        paramUnits.forEach(unit => formData.append("param_unit[]", unit));

        if (btnSaveCatalog) btnSaveCatalog.disabled = true;
        if (saveCatalogBtnText) saveCatalogBtnText.textContent = "Saving...";

        try {
            const response = await fetch("/save-product-scope/", {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            const result = await response.json();

            if (result.status === "success") {
                closeProductModal();
                updateCatalogUI(result.scope, result.created);
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

    if (addProductModalForm) {
        addProductModalForm.addEventListener("submit", handleSaveCatalog);
    }
    btnSaveCatalog?.addEventListener("click", handleSaveCatalog);

    function renderScopeRowHtml(scopeData) {
        const paramsJson = JSON.stringify(scopeData.parameters || []);
        const detailsJson = JSON.stringify({
            id: String(scopeData.id),
            name: scopeData.is_number || "",
            title: scopeData.is_title || "",
            notes: scopeData.description || scopeData.scope_notes || "",
            departments: (scopeData.departments || []).map(d => typeof d === 'string' ? d : d.name)
        });

        const isNum = scopeData.is_number || "Untitled Standard";
        const isTitle = scopeData.is_title && scopeData.is_title !== scopeData.is_number ? scopeData.is_title : "";

        let tagsHtml = "";
        (scopeData.departments || []).forEach(dept => {
            const dname = (typeof dept === 'string' ? dept : dept.name || "").toLowerCase();
            const displayName = typeof dept === 'string' ? dept : dept.name || "";
            let bg = "#F1F5F9", color = "#334155";
            if (dname.includes("chem")) { bg = "#ECFDF5"; color = "#047857"; }
            else if (dname.includes("mech")) { bg = "#F0F9FF"; color = "#0369A1"; }
            else if (dname.includes("metal")) { bg = "#FEF2F2"; color = "#B91C1C"; }
            tagsHtml += `<span class="ps-tag" style="display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 500; background-color: ${bg}; color: ${color};">${escapeHtml(displayName)}</span>`;
        });
        if (!tagsHtml) {
            tagsHtml = `<span class="ps-tag" style="display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 500; background-color: #F1F5F9; color: #334155;">General</span>`;
        }

        return `
            <script type="application/json" class="scope-parameters-json">${paramsJson}</script>
            <script type="application/json" class="scope-details-json">${detailsJson}</script>
            <td style="text-align: center; padding: 16px 8px 16px 16px;">
                <input type="checkbox" class="ps-checkbox">
            </td>
            <td style="padding: 16px;">
                <div class="ps-standard-code" style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 4px;">
                    ${escapeHtml(isNum)}
                </div>
                ${isTitle ? `<div class="ps-standard-desc" style="font-size: 12.5px; line-height: 1.45; color: #64748B;">${escapeHtml(isTitle)}</div>` : ''}
            </td>
            <td style="padding: 16px;">
                <div class="ps-tag-wrap" style="display: flex; flex-direction: column; gap: 6px; align-items: flex-start;">
                    ${tagsHtml}
                </div>
            </td>
            <td style="padding: 16px;">
                <span class="ps-params-text" style="font-size: 13px; font-weight: 600; color: #334155;">
                    ${scopeData.param_count || 0} Params
                </span>
            </td>
            <td style="padding: 16px; text-align: right;">
                <button type="button" class="ps-btn-edit review-product-card__add-btn" data-scope-id="${scopeData.id}" aria-label="Edit Scope" style="background: transparent; border: none; cursor: pointer; padding: 6px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0F3D39" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
            </td>
        `;
    }

    function updateCatalogUI(scopeData, isCreated) {
        if (!scopeData) return;

        const emptyCard = document.getElementById("scopeEmptyCatalogCard");
        if (emptyCard) emptyCard.style.display = "none";

        let psTableBody = document.getElementById("psTableBody");
        if (!psTableBody) {
            const scopeCatalogForm = document.getElementById("scopeCatalogForm");
            if (scopeCatalogForm) {
                scopeCatalogForm.innerHTML = `
                    <div class="products-scope-main-wrapper" id="scopeCatalogContent">
                        <div class="products-scope-toolbar" style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px;">
                            <div class="ps-search-box" style="position: relative; flex: 1;">
                                <svg class="ps-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: 14px; top: 50%; transform: translateY(-50%); pointer-events: none;">
                                    <circle cx="11" cy="11" r="8"></circle>
                                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                </svg>
                                <input type="text" id="psSearchInput" class="ps-search-input" placeholder="Search by standard code or title..." autocomplete="off" style="width: 100%; height: 44px; padding: 0 16px 0 42px; background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; font-size: 14px; color: #0F172A; box-sizing: border-box; outline: none;" />
                            </div>
                            <div class="ps-toolbar-actions" style="display: flex; align-items: center; gap: 10px;">
                                <button type="button" class="btn-ps-filter" id="btnPsFilter" title="Filter Standards" style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; cursor: pointer;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0F172A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                                    </svg>
                                </button>
                                <button type="button" class="btn-ps-add-standard" id="btnAddStandard" style="display: inline-flex; align-items: center; gap: 8px; height: 44px; padding: 0 20px; background-color: #F59E0B; color: #0F172A; border: none; border-radius: 10px; font-size: 14px; font-weight: 700; cursor: pointer; white-space: nowrap;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                        <line x1="12" y1="5" x2="12" y2="19"></line>
                                        <line x1="5" y1="12" x2="19" y2="12"></line>
                                    </svg>
                                    <span>Add Standard</span>
                                </button>
                            </div>
                        </div>
                        <div class="ps-table-wrapper" style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                            <table class="ps-data-table" style="width: 100%; border-collapse: collapse; text-align: left;">
                                <thead>
                                    <tr style="background-color: #F8FAFC; border-bottom: 1px solid #E2E8F0;">
                                        <th style="width: 40px; text-align: center; padding: 14px 16px;"><input type="checkbox" id="selectAllStandards" class="ps-checkbox"></th>
                                        <th style="padding: 14px 16px; font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.04em; text-transform: uppercase;">STANDARD / SPECIFICATION</th>
                                        <th style="padding: 14px 16px; font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.04em; text-transform: uppercase; width: 200px;">CATEGORY</th>
                                        <th style="padding: 14px 16px; font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.04em; text-transform: uppercase; width: 120px;">PARAMETERS</th>
                                        <th style="width: 50px;"></th>
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

        let existingRow = psTableBody?.querySelector(`tr[data-scope-id="${scopeData.id}"]`);
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

    // Live Table Search Filter
    document.addEventListener("input", (e) => {
        if (e.target && e.target.id === "psSearchInput") {
            const query = e.target.value.toLowerCase().trim();
            document.querySelectorAll("#psTableBody tr").forEach(row => {
                const searchAttr = (row.getAttribute("data-search") || "").toLowerCase();
                const textContent = row.textContent.toLowerCase();
                if (searchAttr.includes(query) || textContent.includes(query)) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            });
        }
    });

    // Table Select All Checkboxes
    document.addEventListener("change", (e) => {
        if (e.target && e.target.id === "selectAllStandards") {
            const isChecked = e.target.checked;
            document.querySelectorAll("#psTableBody .ps-checkbox").forEach(cb => {
                cb.checked = isChecked;
            });
        }
    });

    // Add Standard button opens Add Standard popup
    if (btnAddStandard) btnAddStandard.addEventListener("click", () => openProductModal());
    if (btnAddProducts) btnAddProducts.addEventListener("click", () => openProductModal());

    // Add Product Group button opens Testing Packages popup (Requirement 8)
    if (btnAddProductGroup) btnAddProductGroup.addEventListener("click", () => openPackageModal());

    // Close modal on 'X' icon or Cancel button
    if (btnCloseProductModal) btnCloseProductModal.addEventListener("click", closeProductModal);
    if (btnCancelProductModal) btnCancelProductModal.addEventListener("click", closeProductModal);

    // Close modal on backdrop click
    if (addProductModal) {
        addProductModal.addEventListener("click", (e) => {
            if (e.target === addProductModal) closeProductModal();
        });
    }

    // Close modal on Escape key press
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && addProductModal && addProductModal.classList.contains("is-open")) {
            closeProductModal();
        }
    });


    // -------------------------------------------------------------------------
    // Testing Packages Modal & Management Handler
    // -------------------------------------------------------------------------
    const addPackageModal       = document.getElementById("addPackageModal");
    const addPackageModalForm   = document.getElementById("addPackageModalForm");
    const modalPackageId        = document.getElementById("modalPackageId");
    const packageNameInput      = document.getElementById("packageNameInput");
    const packagePriceInput     = document.getElementById("packagePriceInput");
    const packageDiscountInput  = document.getElementById("packageDiscountInput");
    const packageDescInput      = document.getElementById("packageDescInput");
    
    // Unique IDs for Package buttons (To avoid conflict with Add Product buttons)
    const btnAddPackageGroup    = document.getElementById("btnAddPackageGroup");
    const btnEmptyAddPackages   = document.getElementById("btnEmptyAddPackages");
    const btnClosePackageModal  = document.getElementById("btnClosePackageModal");
    const btnCancelPackageModal = document.getElementById("btnCancelPackageModal");

    function openPackageModal(pkgId = "", name = "", price = "", discount = "", desc = "", selectedProductIds = []) {
        if (!addPackageModal) {
            console.error("addPackageModal element not found in DOM!");
            return;
        }
        
        if (modalPackageId) modalPackageId.value = pkgId;
        if (packageNameInput) packageNameInput.value = name;
        if (packagePriceInput) packagePriceInput.value = price;
        if (packageDiscountInput) packageDiscountInput.value = discount;
        if (packageDescInput) packageDescInput.value = desc;

        // Reset and check matching checkboxes for products inside this package
        document.querySelectorAll(".package-product-checkbox").forEach(chk => {
            chk.checked = selectedProductIds.includes(chk.value);
        });

        addPackageModal.classList.add("is-open");
        addPackageModal.setAttribute("aria-hidden", "false");
        if (packageNameInput) packageNameInput.focus();
    }

    function closePackageModal() {
        if (!addPackageModal) return;
        addPackageModal.classList.remove("is-open");
        addPackageModal.setAttribute("aria-hidden", "true");
    }

    // Event Listeners for Opening & Closing Package Modal
    btnAddPackageGroup?.addEventListener("click", () => openPackageModal());
    btnEmptyAddPackages?.addEventListener("click", () => openPackageModal());
    btnClosePackageModal?.addEventListener("click", closePackageModal);
    btnCancelPackageModal?.addEventListener("click", closePackageModal);

    // Close on backdrop click
    addPackageModal?.addEventListener("click", (e) => {
        if (e.target === addPackageModal) closePackageModal();
    });

    // Edit Package Handler (Clicking 'Edit Package' on existing cards)
    document.addEventListener("click", (e) => {
        const editBtn = e.target.closest(".review-edit-package-btn");
        if (!editBtn) return;
        const card = editBtn.closest(".review-product-card");
        const pkgId = card?.getAttribute("data-package-id") || "";
        const title = card?.querySelector(".review-product-card__title")?.textContent.trim() || "";
        const priceText = card?.querySelector(".review-package-price-text")?.textContent || "";
        
        const priceMatch = priceText.match(/₹([\d.]+)/);
        const price = priceMatch ? priceMatch[1] : "";
        const discMatch = priceText.match(/\(([\d.]+)% Off\)/);
        const discount = discMatch ? discMatch[1] : "";

        let productIds = [];
        let description = "";        
        const jsonScript = card?.querySelector(".package-products-json");
        if (jsonScript) {
            try {
                const data = JSON.parse(jsonScript.textContent.trim());

                // Get the package description
                description = data.description || "";

                // Get the selected product IDs
                productIds = (data.products || []).map(
                    product => String(product.id)
                );
            } catch (err) {
                console.error("Error parsing package JSON data:", err);
            }
        } else {
            console.error("Package JSON script not found inside the card.");
        }

        openPackageModal(pkgId, title, price, discount, description, productIds);
    });

    // Handle Form Submit via AJAX (Smart Sync)
    addPackageModalForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const formData = new FormData(addPackageModalForm);
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";
        formData.append("csrfmiddlewaretoken", csrfToken);

        try {
            const response = await fetch("/save-testing-package/", {
                method: "POST",
                body: formData,
                headers: { 
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken
                }
            });
            const result = await response.json();
            if (result.status === "success") {
                closePackageModal();
                window.location.reload(); // Refresh to reflect changes in grid
            } else {
                alert(result.message || "Failed to save package.");
            }
        } catch (err) {
            console.error("Save package error:", err);
            alert("Network error while saving package.");
        }
    });

        // Delete Package Handler
        document.addEventListener("click", async (e) => {
            const dismissBtn = e.target.closest(".review-dismiss-btn");
            if (!dismissBtn) return;
            const card = dismissBtn.closest(".review-product-card");
            if (!card || !card.hasAttribute("data-package-id")) return;

            if (!confirm("Are you sure you want to delete this package?")) return;
            const pkgId = card.getAttribute("data-package-id");
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";

            const formData = new FormData();
            formData.append("package_id", pkgId);
            formData.append("action", "delete_package");
            formData.append("csrfmiddlewaretoken", csrfToken);

            try {
                const response = await fetch(window.location.href, {
                    method: "POST",
                    body: formData,
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                });
                const res = await response.json();
                if (res.status === "success") {
                    card.remove();
                } else {
                    alert(res.message || "Failed to delete package.");
                }
            } catch (err) {
                console.error("Delete package error:", err);
            }
        });

    // -------------------------------------------------------------------------
    // 6. Select and Unselect + / - Tags (Dynamic Re-rendering for Minimum 4 Rule)
    // -------------------------------------------------------------------------
    const PLUS_PATH  = "M9.89319 14.4708L8.10681 14.4708L8.10681 9.87724L3.52923 9.89319V8.10681L8.12276 8.10681L8.10681 3.52923L9.89319 3.52923L9.87724 8.10681L14.4708 8.10681V9.89319L9.89319 9.87724L9.89319 14.4708Z";
    const MINUS_PATH = "M9.89319 9.87724L8.10681 9.87724L3.52923 9.89319V8.10681H8.12276L8.09086 8.10681L9.87724 8.10681L14.4708 8.10681V9.89319L9.89319 9.87724Z";

    const disciplinesWrap = document.getElementById("disciplinesWrap");
    const disciplinesChips = document.getElementById("disciplinesChips");

    const departmentsWrap = document.getElementById("testingTypesWrap");
    const departmentsChips = document.getElementById("typesChips");

    const categoriesWrap = document.getElementById("categoriesWrap");
    const categoriesChips = document.getElementById("categoriesChips");

    const subcategoriesWrap = document.getElementById("subcategoriesWrap");
    const subcategoriesChips = document.getElementById("subcategoriesChips");


    // Return all selected category IDs.
    function getSelectedCategoryIds() {
        return new Set(
            Array.from(
                document.querySelectorAll(
                    "#categoriesWrap .review-tag-pill--selected, " +
                    "#categoriesChips .review-tag-pill--selected"
                )
            )
            .map(chip => chip.dataset.categoryId)
            .filter(Boolean)
        );
    }


    // Update the + / - icon and aria-pressed state.
    function updateTagIcon(chip) {
        const selected = chip.classList.contains("review-tag-pill--selected");
        const path = chip.querySelector("svg path");
        if (path) {
            path.setAttribute("d", selected ? MINUS_PATH : PLUS_PATH);
        }

        chip.setAttribute("aria-pressed", String(selected));
    }


    // Synchronize the same tag across the visible section and dropdown.
    function syncTagState(tagType, id, selected) {
        let selector = "";
        if (tagType === "discipline") {
            selector = "#disciplinesWrap .review-tag-pill, #disciplinesChips .review-tag-pill";
        } else if (tagType === "department") {
            selector = "#testingTypesWrap .review-tag-pill, #typesChips .review-tag-pill";
        } else if (tagType === "category") {
            selector = "#categoriesWrap .review-tag-pill, #categoriesChips .review-tag-pill";
        } else if (tagType === "subcategory") {
            selector = "#subcategoriesWrap .review-tag-pill, #subcategoriesChips .review-tag-pill";
        }

        document.querySelectorAll(selector).forEach(chip => {
            let chipId = "";
            if (tagType === "discipline") chipId = chip.dataset.disciplineId;
            else if (tagType === "department") chipId = chip.dataset.departmentId;
            else if (tagType === "category") chipId = chip.dataset.categoryId;
            else if (tagType === "subcategory") chipId = chip.dataset.subcategoryId;

            if (String(chipId) !== String(id)) {
                return;
            }

            chip.classList.toggle("review-tag-pill--selected", selected);
            updateTagIcon(chip);
        });
    }


    // Render selected tags first, then pad to at least four visible tags.
    function refreshVisibleTags(container, chipContainer) {
        if (!container || !chipContainer) {
            return;
        }

        const allChips = Array.from(
            chipContainer.querySelectorAll(".review-tag-pill")
        );

        const selectedChips = allChips.filter(chip =>
            chip.classList.contains("review-tag-pill--selected")
        );

        const unselectedChips = allChips.filter(chip =>
            !chip.classList.contains("review-tag-pill--selected")
        );

        const displayList = [
            ...selectedChips,
            ...unselectedChips.slice(
                0,
                Math.max(0, 4 - selectedChips.length)
            )
        ];

        container.replaceChildren();

        displayList.forEach(chip => {
            const clone = chip.cloneNode(true);
            updateTagIcon(clone);
            container.appendChild(clone);
        });
    }


    // Filter subcategories according to selected categories (like Discipline/Department).
    function filterSubcategories() {
        const selectedCategoryIds = getSelectedCategoryIds();

        if (!subcategoriesChips || !subcategoriesWrap) {
            return;
        }
        const allSubcategoryChips = Array.from(
            subcategoriesChips.querySelectorAll(".review-tag-pill")
        );

        const noCategorySelected = selectedCategoryIds.size === 0;

        // 1. Toggle visibility of the "Add Subcategory" button container
        const subcategoryAnchor = subcategoriesWrap.nextElementSibling;
        if (subcategoryAnchor && subcategoryAnchor.classList.contains("review-disciplines-anchor")) {
            subcategoryAnchor.style.display = noCategorySelected ? "none" : "";
        }

        // 2. Hide/clear dropdown options and deselect tags if no category selected
        allSubcategoryChips.forEach(chip => {
            const belongsToSelectedCategory =
                !noCategorySelected &&
                selectedCategoryIds.has(String(chip.dataset.categoryId));

            chip.hidden = !belongsToSelectedCategory;
            chip.style.display = belongsToSelectedCategory ? "" : "none";

            if (!belongsToSelectedCategory && chip.classList.contains("review-tag-pill--selected")) {
                chip.classList.remove("review-tag-pill--selected");
                updateTagIcon(chip);
            }
        });

        // 3. Clear visible subcategory pills when no category is selected
        if (noCategorySelected) {
            subcategoriesWrap.innerHTML = '<p class="review-empty-hint" style="color: #64748B; font-size: 13px; margin: 4px 0;">Please select a category above to view subcategories.</p>';
            return;
        }

        // 4. Populate matching subcategories when a category is selected (up to 4)
        const matchingChips = allSubcategoryChips.filter(chip =>
            selectedCategoryIds.has(String(chip.dataset.categoryId))
        );

    const selectedChips = matchingChips.filter(chip =>
        chip.classList.contains("review-tag-pill--selected")
    );
    const unselectedChips = matchingChips.filter(chip =>
        !chip.classList.contains("review-tag-pill--selected")
    );

    const displayList = [
        ...selectedChips,
        ...unselectedChips.slice(0, Math.max(0, 4 - selectedChips.length))
    ];

    subcategoriesWrap.replaceChildren();
    displayList.forEach(chip => {
        const clone = chip.cloneNode(true);
        clone.hidden = false;
        clone.style.display = "";
        updateTagIcon(clone);
        subcategoriesWrap.appendChild(clone);
    });
}

    // Save all currently selected disciplines.
    async function saveSelectedDisciplines() {
        if (!disciplinesChips) return;
        const formData = new FormData();
        const selectedNames = new Set();
        disciplinesChips.querySelectorAll(".review-tag-pill--selected").forEach(chip => {
            selectedNames.add(chip.dataset.tag.trim());
        });
        selectedNames.forEach(name => {
            formData.append("disciplines[]", name);
        });
        return await sendAutoSave("save_disciplines", formData);
    }


    // Save all currently selected departments (independent of discipline selection).
    async function saveSelectedDepartments() {
        if (!departmentsChips) return;
        const formData = new FormData();
        const selectedNames = new Set();
        departmentsChips.querySelectorAll(".review-tag-pill--selected").forEach(chip => {
            selectedNames.add(chip.dataset.tag.trim());
        });
        selectedNames.forEach(name => {
            formData.append("departments[]", name);
        });
        return await sendAutoSave("save_departments", formData);
    }


    // Save all currently selected categories.
    async function saveSelectedCategories() {
        if (!categoriesChips) return;
        const formData = new FormData();
        const selectedNames = new Set();
        categoriesChips.querySelectorAll(".review-tag-pill--selected").forEach(chip => {
            selectedNames.add(chip.dataset.tag.trim());
        });
        selectedNames.forEach(name => {
            formData.append("categories[]", name);
        });
        return await sendAutoSave("save_categories", formData);
    }


    // Save subcategories that belong to currently selected categories.
    async function saveSelectedSubcategories() {
        if (!subcategoriesChips) return;
        const selectedCategoryIds = getSelectedCategoryIds();
        const formData = new FormData();
        const selectedNames = new Set();

        subcategoriesChips.querySelectorAll(".review-tag-pill--selected").forEach(chip => {
            if (
                selectedCategoryIds.size > 0 &&
                selectedCategoryIds.has(String(chip.dataset.categoryId))
            ) {
                selectedNames.add(chip.dataset.tag.trim());
            }
        });

        selectedNames.forEach(name => {
            formData.append("subcategories[]", name);
        });
        return await sendAutoSave("save_subcategories", formData);
    }


    // Initial setup for tags:
    refreshVisibleTags(disciplinesWrap, disciplinesChips);
    refreshVisibleTags(departmentsWrap, departmentsChips); // Departments are independent of discipline!
    refreshVisibleTags(categoriesWrap, categoriesChips);
    filterSubcategories(); // Subcategories are filtered according to category!


    // Handle clicks on dynamically rendered tag pills (Discipline, Department, Category, SubCategory).
    document.addEventListener("click", async event => {
        const tag = event.target.closest(".review-tag-pill");
        if (!tag) return;

        const isDiscipline = Boolean(tag.closest("#disciplinesWrap, #disciplinesChips"));
        const isDepartment = Boolean(tag.closest("#testingTypesWrap, #typesChips"));
        const isCategory = Boolean(tag.closest("#categoriesWrap, #categoriesChips"));
        const isSubcategory = Boolean(tag.closest("#subcategoriesWrap, #subcategoriesChips"));

        if (!isDiscipline && !isDepartment && !isCategory && !isSubcategory) {
            return;
        }

        let tagType = "";
        let tagId = "";
        if (isDiscipline) {
            tagType = "discipline";
            tagId = tag.dataset.disciplineId;
        } else if (isDepartment) {
            tagType = "department";
            tagId = tag.dataset.departmentId;
        } else if (isCategory) {
            tagType = "category";
            tagId = tag.dataset.categoryId;
        } else if (isSubcategory) {
            tagType = "subcategory";
            tagId = tag.dataset.subcategoryId;
        }

        if (!tagId) {
            console.error(`Missing id on tag:`, tag);
            return;
        }

        const isSelected = !tag.classList.contains("review-tag-pill--selected");

        if (isDiscipline) {
            syncTagState("discipline", tagId, isSelected);
            refreshVisibleTags(disciplinesWrap, disciplinesChips);
            // Departments are now independent of discipline! Do not touch or filter departments!
            await saveSelectedDisciplines();

        } else if (isDepartment) {
            // Departments are independent of discipline selection!
            syncTagState("department", tagId, isSelected);
            refreshVisibleTags(departmentsWrap, departmentsChips);
            await saveSelectedDepartments();

        } else if (isCategory) {
            syncTagState("category", tagId, isSelected);
            refreshVisibleTags(categoriesWrap, categoriesChips);
            // Subcategories depend on Category selection!
            filterSubcategories();
            await saveSelectedCategories();
            await saveSelectedSubcategories();

        } else if (isSubcategory) {
            // Subcategory according to category: prevent selecting subcategory if parent category not selected
            const selectedCategoryIds = getSelectedCategoryIds();
            if (
                selectedCategoryIds.size === 0 ||
                !selectedCategoryIds.has(String(tag.dataset.categoryId))
            ) {
                syncTagState("subcategory", tagId, false);
                return;
            }

            syncTagState("subcategory", tagId, isSelected);
            filterSubcategories();
            await saveSelectedSubcategories();
        }
    });
    
    // -------------------------------------------------------------------------
    // 7. Detailed Services & Accreditations (Instant Auto-Save & Add)
    // -------------------------------------------------------------------------
    const servicesList = document.getElementById("servicesList");
    const btnAddService = document.getElementById("btnAddService");
    const btnEmptyAddServices = document.getElementById("btnEmptyAddServices");
    const accredList = document.getElementById("accreditationsList");
    const btnAddCert = document.getElementById("btnAddCertificate");

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
        const nameInput = card.querySelector(".review-service-input-title, .review-service-card__title");
        const descInput = card.querySelector(".review-service-input-desc, .review-service-card__desc");
        const name = nameInput ? (nameInput.value !== undefined ? nameInput.value : nameInput.textContent).trim() : "";
        const desc = descInput ? (descInput.value !== undefined ? descInput.value : descInput.textContent).trim() : "";
        
        if (!name) return;
        const formData = new FormData();
        if (card.dataset.id) formData.append("service_id", card.dataset.id);
        formData.append("name", name);
        formData.append("service_description", desc);
        const res = await sendAutoSave("save_services", formData);
        if (res && res.service_id) card.dataset.id = res.service_id;
    }

    // Incorrect (causes syntax error):
    document.addEventListener("blur", async (e) => {
        if (e.target.matches(".review-service-input-title, .review-service-input-desc")) {
            await saveServiceCard(e.target.closest(".review-service-card"));
        }
    }, true);

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
        const body = row.querySelector("[name='accreditation_body']").value.trim();
        const certNo = row.querySelector("[name='certificate_no']").value.trim();
        const validity = row.querySelector("[name='validity_date']").value;
        const logoInput = row.querySelector(".review-accred-logo-input");

        if (!body && !certNo) return;
        const formData = new FormData();
        if (row.dataset.id) formData.append("accred_id", row.dataset.id);
        formData.append("accreditation_body", body);
        formData.append("certificate_no", certNo);
        formData.append("validity_date", validity);
        if (logoInput?.files?.[0]) formData.append("accreditation_logo", logoInput.files[0]);

        const res = await sendAutoSave("save_accreditation", formData);
        if (res && res.accred_id) row.dataset.id = res.accred_id;
    }

    document.addEventListener("blur", async (e) => {
        if (e.target.matches(".review-accred-input")) {
            await saveAccredRow(e.target.closest(".review-accreditation-row"));
        }
    }, true);

    function getGeneralInputs() {
        return Array.from(document.querySelectorAll("#sectionBasicInfo input:not([type=file]), #sectionBasicInfo select, #sectionAbout textarea"))
            .filter(el => !el.closest("#socialMediaDropdown") && !el.classList.contains("dynamic-category-input"));
    }

    // -------------------------------------------------------------------------
    // 8. General Fields Auto-Save on Blur/Change
    // -------------------------------------------------------------------------
    getGeneralInputs().forEach(input => {
        input.addEventListener("change", async () => {
            const formData = new FormData();
            getGeneralInputs().forEach(el => formData.append(el.name, el.value));
            await sendAutoSave("save_general", formData);
        });
    });
    

    

    // Social Media Links & Auto-Save
    const socialIcons = document.getElementById("socialMediaIcons");

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
                // html.push(<a href= `${url}` target="_blank" rel="noopener noreferrer" class="review-social-btn" aria-label=`${platform}`><img src="/static/images/social_${platform}.svg" alt="${platform}" width="30" height="30"></a>);
                html.push(`
                <a href="${url}"
                target="_blank"
                rel="noopener noreferrer"
                class="review-social-btn"
                aria-label="${platform}">
                    <img src="/static/images/social_${platform}.svg"
                        alt="${platform}"
                        width="30"
                        height="30">
                </a>
            `);
            }
        });

        if (socialIcons) {
            socialIcons.innerHTML = html.length ? html.join("") : "<p>No social media links available. Add some below.</p>";
        }
        await sendAutoSave("save_socials", fd);
    });


    // Laboratory Logo Upload Preview & Auto-Save
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

    // 9. Cross Dismiss Handler for Deletions
    document.addEventListener("click", async (e) => {
        const dismissBtn = e.target.closest(".review-dismiss-btn");
        if (!dismissBtn) return;

        const serviceCard = dismissBtn.closest(".review-service-card");
        const accredRow = dismissBtn.closest(".review-accreditation-row");
        const photoSlot = dismissBtn.closest(".review-photo-slot");
        const productCard = dismissBtn.closest(".review-product-card");

        if (serviceCard) {
            const serviceId = serviceCard.dataset.id;
            if (serviceId) {
                const fd = new FormData();
                fd.append("service_id", serviceId);
                await sendAutoSave("delete_service", fd);
            }
            serviceCard.remove();
        }
        if (accredRow) {
            const accredId = accredRow.dataset.id;
            if (accredId) {
                const fd = new FormData();
                fd.append("accred_id", accredId);
                await sendAutoSave("delete_accreditation", fd);
            }
            accredRow.remove();
        }
        if (photoSlot) {
            const photoId = photoSlot.dataset.id;
            if (photoId) {
                const fd = new FormData();
                fd.append("photo_id", photoId);
                await sendAutoSave("delete_photo", fd);
            }
            photoSlot.remove();
            updatePhotoPlaceholders();
        }

        // product delete handler
        if (productCard) {
            const scopeId = productCard.dataset.scopeId;
            if (scopeId) {
                const fd = new FormData();
                fd.append("scope_id", scopeId);
                await sendAutoSave("delete_scope", fd);
            }
            productCard.remove();
            const grid = document.getElementById("productsGrid");
            if (grid) {
                const remainingCards = grid.querySelectorAll(".review-product-card");
                if (remainingCards.length === 0) {
                    const emptyTabMsg = document.getElementById("scopeTabEmptyMessage");
                    if (emptyTabMsg) emptyTabMsg.style.display = "block";
                }
            }
        }
    });

     // 10. Facility Photos Upload
    const photoInput = document.getElementById("facilityPhotoInput");

    function updatePhotoPlaceholders() {
        const grid = document.querySelector(".review-photos-grid");
        if (!grid) return;
        const photoCount = grid.querySelectorAll(".review-photo-slot").length;
        const remainingNeeded = Math.max(0, 4 - photoCount);
        let placeholders = Array.from(grid.querySelectorAll(".review-photo-placeholder-slot"));

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
        if (!files.length) return;
        const formData = new FormData();
        Array.from(files).forEach(f => formData.append("facility_photos", f));
        const res = await sendAutoSave("upload_photo", formData);
        if (res && res.status === "success" && res.photos) {
            const grid = document.querySelector(".review-photos-grid");
            const firstPlaceholder = grid.querySelector(".review-photo-placeholder-slot");
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
                if (firstPlaceholder) {
                    grid.insertBefore(slot, firstPlaceholder);
                } else {
                    grid.appendChild(slot);
                }
            });
            updatePhotoPlaceholders();
        }
        photoInput.value = "";
    });

    // -------------------------------------------------------------------------
    // 11. Scope Catalog Discipline Filters
    // -------------------------------------------------------------------------
    const scopeFilters = document.querySelectorAll(".review-scope-filter");

    function applyScopeFilter(filterValue, activeBtn) {
        // Update active tab buttons and aria attributes
        scopeFilters.forEach((btn) => {
            const isActive = btn === activeBtn;
            btn.classList.toggle("review-scope-filter--active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });

        // Filter product cards in the grid
        const productCards = document.querySelectorAll("#productsGrid .review-product-card");

        productCards.forEach((card) => {
            const rawCategories = (card.getAttribute("data-category") || "").toLowerCase();
            const categories = rawCategories.split(/\s+/).filter(Boolean);
            const tagTexts = Array.from(card.querySelectorAll(".review-product-tag span"))
                .map((s) => s.textContent.trim().toLowerCase());

            const isMatch = filterValue === "all" ||
                categories.includes(filterValue) ||
                tagTexts.some((tag) => tag.includes(filterValue));

            card.style.display = isMatch ? "" : "none";
        });
    }

    scopeFilters.forEach((btn, index) => {
        btn.addEventListener("click", () => {
            const filterValue = (btn.getAttribute("data-filter") || "all").toLowerCase();
            applyScopeFilter(filterValue, btn);
        });

        // Keyboard navigation (ArrowLeft / ArrowRight / Home / End) for WAI-ARIA tablist
        btn.addEventListener("keydown", (e) => {
            let targetIndex = null;
            if (e.key === "ArrowRight") {
                targetIndex = (index + 1) % scopeFilters.length;
            } else if (e.key === "ArrowLeft") {
                targetIndex = (index - 1 + scopeFilters.length) % scopeFilters.length;
            } else if (e.key === "Home") {
                targetIndex = 0;
            } else if (e.key === "End") {
                targetIndex = scopeFilters.length - 1;
            }

            if (targetIndex !== null) {
                e.preventDefault();
                const targetBtn = scopeFilters[targetIndex];
                targetBtn.focus();
                const filterValue = (targetBtn.getAttribute("data-filter") || "all").toLowerCase();
                applyScopeFilter(filterValue, targetBtn);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 12. Custom Searchable Dropdown for review-field-card (Country / State)
    // -------------------------------------------------------------------------
    document.querySelectorAll(".review-custom-select:not(#labCategoryFieldCard)").forEach(cs => {
        const dropdown = cs.querySelector(".review-custom-select__dropdown");
        const searchInput = cs.querySelector(".review-custom-select__search");
        const valueSpan = cs.querySelector(".review-custom-select__value");
        const nativeSelect = cs.querySelector(".review-custom-select__native");

        cs.addEventListener("click", (e) => {
            if (e.target.closest(".review-custom-select__dropdown")) return;
            const isOpen = cs.classList.toggle("is-open");
            if (dropdown) dropdown.hidden = !isOpen;
            if (isOpen && searchInput) {
                searchInput.value = "";
                cs.querySelectorAll(".review-custom-select__option").forEach(o => o.style.display = "");
                setTimeout(() => searchInput.focus(), 50);
            }
        });

        // Search filtering
        searchInput?.addEventListener("input", (e) => {
            const q = e.target.value.toLowerCase().trim();
            cs.querySelectorAll(".review-custom-select__option").forEach(opt => {
                opt.style.display = opt.textContent.toLowerCase().includes(q) ? "" : "none";
                opt.classList.remove("is-highlighted");
            });
        });

        // Keyboard navigation (Escape, Enter, Arrows)
        cs.addEventListener("keydown", (e) => {
            const isOpen = cs.classList.contains("is-open");
            const visibleOpts = Array.from(cs.querySelectorAll(".review-custom-select__option"))
                .filter(o => o.style.display !== "none");

            if (e.key === "Escape") {
                cs.classList.remove("is-open");
                dropdown.hidden = true;
            } else if (e.key === "Enter" || (e.key === " " && !isOpen && e.target !== searchInput)) {
                e.preventDefault();
                if (!isOpen) {
                    cs.click();
                } else {
                    const activeOpt = visibleOpts.find(o => o.classList.contains("is-highlighted")) || visibleOpts[0];
                    if (activeOpt) activeOpt.click();
                }
            } else if (isOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
                e.preventDefault();
                let idx = visibleOpts.findIndex(o => o.classList.contains("is-highlighted"));
                visibleOpts.forEach(o => o.classList.remove("is-highlighted"));
                idx = e.key === "ArrowDown" 
                    ? (idx < visibleOpts.length - 1 ? idx + 1 : 0)
                    : (idx > 0 ? idx - 1 : visibleOpts.length - 1);
                const target = visibleOpts[idx];
                if (target) {
                    target.classList.add("is-highlighted");
                    target.scrollIntoView({ block: "nearest" });
                }
            }
        });

        // Option select & auto-save
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

    // Close on outside click
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".review-custom-select")) {
            document.querySelectorAll(".review-custom-select").forEach(cs => {
                cs.classList.remove("is-open");
                const dd = cs.querySelector(".review-custom-select__dropdown");
                if (dd) dd.hidden = true;
            });
        }
    });

    });

document.addEventListener("click", async (e) => {
    const btnSubmitApproval = e.target.closest("#btnSubmitApproval");
    if (!btnSubmitApproval) return;

    if (!confirm("Are you sure you want to submit your profile for approval?")) return;

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";
    const formData = new FormData();
    formData.append("action", "submit_for_approval");
    formData.append("csrfmiddlewaretoken", csrfToken);

    try {
        const response = await window.fetch(window.location.href, {
            method: "POST",
            body: formData,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });
        const res = await response.json();
        
        if (res && res.status === "success") {
            alert(res.message || "Profile submitted for approval successfully!");
            window.location.href = "/lab-review-detail/";
        } else {
            alert(res?.message || "Failed to submit profile. Please try again.");
        }
    } catch (err) {
        console.error("Submit approval error:", err);
        alert("Network error while submitting profile.");
    }
});


// -------------------------------------------------------------------------
// 13. Lab Category Dropdown & Dynamic Category Fields Auto-Save
// -------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------------------
    // 1. DOM Elements & References
    // -------------------------------------------------------------------------
    const categorySelect = document.getElementById("facilityLabCategory");
    const categoryModal = document.getElementById("categoryChangeModal");
    const btnCancelCategoryChange = document.getElementById("btnCancelCategoryChange");
    const btnConfirmCategoryChange = document.getElementById("btnConfirmCategoryChange");
    
    let pendingCatId = null;

    // -------------------------------------------------------------------------
    // 2. Helper Functions
    // -------------------------------------------------------------------------
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === name + "=") {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async function sendAutoSave(action, formData) {
        formData.append("action", action);
        const csrfToken = getCookie("csrftoken") || document.querySelector('[name=csrfmiddlewaretoken]')?.value || "";

        try {
            const response = await fetch(window.location.href, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Auto-save failed for action [${action}]:`, error);
            return null;
        }
    }

    // -------------------------------------------------------------------------
    // 3. Modal Control Functions
    // -------------------------------------------------------------------------
    function openCategoryModal() {
        if (!categoryModal) return;
        categoryModal.classList.add("is-open");
        categoryModal.setAttribute("aria-hidden", "false");
    }

    function closeCategoryModal() {
        if (!categoryModal) return;
        categoryModal.classList.remove("is-open");
        categoryModal.setAttribute("aria-hidden", "true");
    }

    // -------------------------------------------------------------------------
    // 4. Dynamic Field Rendering & Auto-Save
    // -------------------------------------------------------------------------
    function bindDynamicCategoryInputEvents() {
        const dynamicInputs = document.querySelectorAll(".dynamic-category-input");
        if (!dynamicInputs.length) return;

        const saveCategoryData = async () => {
            const formData = new FormData();
            document.querySelectorAll(".dynamic-category-input").forEach((el) => {
                const key = el.getAttribute("data-key");
                if (key) {
                    formData.append(`category_data[${key}]`, el.value);
                }
            });

            await sendAutoSave("save_category_data", formData);
        };

        dynamicInputs.forEach((input) => {
            const tagName = input.tagName.toLowerCase();

            if (tagName === "select") {
                input.removeEventListener("change", saveCategoryData);
                input.addEventListener("change", saveCategoryData);
            } else {
                input.removeEventListener("blur", saveCategoryData);
                input.addEventListener("blur", saveCategoryData);

                if (tagName === "input" && input.getAttribute("type") !== "textarea") {
                    input.addEventListener("keydown", (e) => {
                        if (e.key === "Enter") {
                            e.preventDefault();
                            input.blur();
                        }
                    });
                }
            }
        });
    }

    function renderDynamicCategoryFields(catName, fields, values) {
        const section = document.getElementById("sectionCategorySpecific");
        const container = document.getElementById("dynamicCategoryFieldsContainer");
        const titleSpan = document.getElementById("dynCategoryTitle");
        const descSpan = document.getElementById("dynCategoryDescName");

        // Fallback array check
        const fieldList = fields || [];

        if (!Array.isArray(fieldList) || fieldList.length === 0) {
            if (section) section.style.display = "none";
            if (container) container.innerHTML = "";
            return;
        }

        if (titleSpan) titleSpan.textContent = catName || "";
        if (descSpan) descSpan.textContent = catName || "";
        if (container) container.innerHTML = "";

        fieldList.forEach((field) => {
            const val = values && values[field.key] !== undefined ? values[field.key] : "";
            const requiredStar = field.required ? '<span style="color:red;">*</span>' : "";
            const card = document.createElement("div");
            card.className = "review-field-card";

            let inputHtml = "";
            if (field.type === "boolean") {
                const isTrue = String(val) === "true";
                inputHtml = `
                    <select id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}">
                        <option value="true" ${isTrue ? "selected" : ""}>Yes</option>
                        <option value="false" ${!isTrue ? "selected" : ""}>No</option>
                    </select>`;
            } else if (field.type === "number") {
                inputHtml = `<input type="number" step="any" id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}" value="${val}" placeholder="${field.placeholder || ""}">`;
            } else if (field.type === "textarea") {
                inputHtml = `<textarea id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}" rows="3" placeholder="${field.placeholder || ""}">${val}</textarea>`;
            } else {
                inputHtml = `<input type="text" id="dyn_${field.key}" name="category_data[${field.key}]" class="review-field-input dynamic-category-input" data-key="${field.key}" value="${val}" placeholder="${field.placeholder || ""}">`;
            }

            card.innerHTML = `
                <label for="dyn_${field.key}" class="review-field-label review-field-label--slate">
                    ${field.label} ${requiredStar}
                </label>
                ${inputHtml}
            `;
            container.appendChild(card);
        });

        if (section) section.style.display = "block";

        // Bind dynamic input listeners
        bindDynamicCategoryInputEvents();
    }

    async function triggerCategorySave() {
        const formData = new FormData();

        // 1. Gather all general inputs inside tab-general
        const generalContainer = document.getElementById("tab-general") || document;
        const inputs = generalContainer.querySelectorAll("input, select, textarea");
        
        inputs.forEach((el) => {
            if (el.name && !el.disabled) {
                formData.append(el.name, el.value);
            }
        });

        // 2. CRITICAL FIX: Always explicitly append lab_category and lab_category_id
        if (categorySelect) {
            const selectedCatVal = categorySelect.value;
            formData.set("lab_category", selectedCatVal);
            formData.set("lab_category_id", selectedCatVal);
            formData.set("facility_lab_category", selectedCatVal);
        }

        const res = await sendAutoSave("save_general", formData);

        if (res && (res.status === "success" || res.status === 200 || res.success)) {
            const updatedCatId = res.category_id || (categorySelect ? categorySelect.value : "");

            if (categorySelect) {
                categorySelect.value = updatedCatId;
                categorySelect.setAttribute("data-current-category-id", updatedCatId);
            }

            // Extract schema fields dynamically supporting multiple API payload formats
            const responseFields = res.fields || res.category_fields || res.schema || [];
            const responseValues = res.category_data || res.values || {};
            const categoryName = res.category_name || (categorySelect ? categorySelect.options[categorySelect.selectedIndex]?.text : "");

            renderDynamicCategoryFields(categoryName, responseFields, responseValues);
        }
    }

    // -------------------------------------------------------------------------
    // 5. Category Selection Listeners
    // -------------------------------------------------------------------------
    if (categorySelect) {
        categorySelect.addEventListener("change", async () => {
            const newCatId = categorySelect.value;
            const currentCatId = categorySelect.getAttribute("data-current-category-id");

            if (!newCatId) return;

            if (currentCatId && String(currentCatId).trim() !== "" && String(currentCatId) !== String(newCatId)) {
                pendingCatId = newCatId;
                openCategoryModal();
            } else {
                await triggerCategorySave();
            }
        });
    }

    btnCancelCategoryChange?.addEventListener("click", () => {
        closeCategoryModal();
        if (categorySelect) {
            categorySelect.value = categorySelect.getAttribute("data-current-category-id") || "";
        }
        pendingCatId = null;
    });

    btnConfirmCategoryChange?.addEventListener("click", async () => {
        closeCategoryModal();
        if (pendingCatId && categorySelect) {
            categorySelect.value = pendingCatId;
            await triggerCategorySave();
        }
    });

    // Initial load binding
    bindDynamicCategoryInputEvents();
});
// -------------------------------------------------------------------------
// Cascading Custom Select: Discipline -> Department
// -------------------------------------------------------------------------
// const disciplineCard = document.getElementById("disciplineFieldCard");
// const departmentCard = document.getElementById("departmentFieldCard");
// const nativeDisciplineSelect = document.getElementById("facilityDiscipline");
// const nativeDepartmentSelect = document.getElementById("facilityDepartment");
// const selectedDisciplineVal = document.getElementById("selectedDisciplineValue");
// const selectedDepartmentVal = document.getElementById("selectedDepartmentValue");
// const departmentOptionsList = document.getElementById("departmentOptionsList");

// if (disciplineCard && departmentCard && nativeDisciplineSelect) {
//     nativeDisciplineSelect.addEventListener("change", async function () {
//         const disciplineId = this.value;

//         // Reset department selection
//         nativeDepartmentSelect.innerHTML = '<option value="">Select Department</option>';
//         if (selectedDepartmentVal) {
//             selectedDepartmentVal.textContent = "Select Department";
//             selectedDepartmentVal.classList.add("review-custom-select__value--placeholder");
//         }
//         if (departmentOptionsList) {
//             departmentOptionsList.innerHTML = '<div class="review-custom-select__empty">No departments found</div>';
//         }

//         // Disable department card if no discipline selected
//         if (!disciplineId) {
//             departmentCard.style.opacity = "0.6";
//             departmentCard.style.pointerEvents = "none";
//             departmentCard.setAttribute("aria-disabled", "true");
//             return;
//         }

//         try {
//             const response = await fetch(`/api/get-departments/?discipline_id=${disciplineId}`, {
//                 headers: { "X-Requested-With": "XMLHttpRequest" }
//             });
//             const data = await response.json();

//             if (data.status === "success" && data.departments.length > 0) {
//                 let optionsHtml = "";
//                 let nativeOptionsHtml = '<option value="">Select Department</option>';

//                 data.departments.forEach(dept => {
//                     nativeOptionsHtml += `<option value="${dept.id}">${dept.name}</option>`;
//                     optionsHtml += `<div class="review-custom-select__option" data-value="${dept.id}" role="option" aria-selected="false">${dept.name}</div>`;
//                 });

//                 nativeDepartmentSelect.innerHTML = nativeOptionsHtml;
//                 departmentOptionsList.innerHTML = optionsHtml;

//                 // Enable department card
//                 departmentCard.style.opacity = "1";
//                 departmentCard.style.pointerEvents = "";
//                 departmentCard.removeAttribute("aria-disabled");
//             } else {
//                 departmentOptionsList.innerHTML = '<div class="review-custom-select__empty" style="display:block;">No departments found</div>';
//             }
//         } catch (err) {
//             console.error("Error fetching dependent departments:", err);
//         }
//     });
// }


// -------------------------------------------------------------------------
    // Test Disciplines & Testing Types (Departments) Tag Click & Auto-Save Handler
    // -------------------------------------------------------------------------