/**
 * verify-email.js
 * Handles 5-digit OTP input auto-advance, backspace navigation, paste splitting, and countdown timer.
 */
document.addEventListener("DOMContentLoaded", () => {
    const otpInputs = document.querySelectorAll(".auth-otp-input");
    const resendTimerEl = document.getElementById("resendTimer");
    const targetEmailEl = document.querySelector(".auth-target-email");

    // Display query param email if available
    const urlParams = new URLSearchParams(window.location.search);
    const emailParam = urlParams.get("email");
    if (emailParam && targetEmailEl) {
        targetEmailEl.textContent = emailParam;
    }

    // OTP Input Navigation
    otpInputs.forEach((input, index) => {
        // Handle input typing
        input.addEventListener("input", (e) => {
            const val = e.target.value.replace(/\D/g, "");
            e.target.value = val ? val[0] : "";

            if (val && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus();
            }
        });

        // Handle keyboard navigation (Backspace, Left/Right arrows)
        input.addEventListener("keydown", (e) => {
            if (e.key === "Backspace") {
                if (!input.value && index > 0) {
                    otpInputs[index - 1].focus();
                }
            } else if (e.key === "ArrowLeft" && index > 0) {
                otpInputs[index - 1].focus();
            } else if (e.key === "ArrowRight" && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus();
            }
        });

        // Handle paste across all inputs
        input.addEventListener("paste", (e) => {
            e.preventDefault();
            const pasteData = (e.clipboardData || window.clipboardData)
                .getData("text")
                .replace(/\D/g, "")
                .slice(0, otpInputs.length);

            if (pasteData) {
                pasteData.split("").forEach((char, i) => {
                    if (otpInputs[i]) {
                        otpInputs[i].value = char;
                    }
                });
                const nextFocus = Math.min(pasteData.length, otpInputs.length - 1);
                otpInputs[nextFocus].focus();
            }
        });
    });

    // 60s Countdown Timer with Resend Restart
    const resendLabelEl = document.getElementById("resendLabel");
    let countdownInterval = null;

    function startResendTimer(duration = 60) {
        if (!resendTimerEl) return;

        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }

        let timeLeft = duration;
        resendTimerEl.classList.remove("is-clickable");
        resendTimerEl.removeAttribute("role");
        resendTimerEl.removeAttribute("tabindex");

        if (resendLabelEl) {
            resendLabelEl.textContent = "Resend in ";
        }

        const renderTime = (secondsLeft) => {
            const minutes = Math.floor(secondsLeft / 60).toString().padStart(2, "0");
            const seconds = (secondsLeft % 60).toString().padStart(2, "0");
            resendTimerEl.textContent = `${minutes}:${seconds}`;
        };

        renderTime(timeLeft);

        countdownInterval = setInterval(() => {
            timeLeft--;
            if (timeLeft <= 0) {
                clearInterval(countdownInterval);
                countdownInterval = null;
                if (resendLabelEl) {
                    resendLabelEl.textContent = "";
                }
                resendTimerEl.textContent = "Resend OTP";
                resendTimerEl.classList.add("is-clickable");
                resendTimerEl.setAttribute("role", "button");
                resendTimerEl.setAttribute("tabindex", "0");
            } else {
                renderTime(timeLeft);
            }
        }, 1000);
    }

    if (resendTimerEl) {
        // Click to resend and restart timer
        resendTimerEl.addEventListener("click", () => {
            if (resendTimerEl.classList.contains("is-clickable")) {
                startResendTimer(60);

                // Clear and autofocus first digit
                if (otpInputs && otpInputs.length > 0) {
                    otpInputs.forEach((input) => (input.value = ""));
                    otpInputs[0].focus();
                }

                if (typeof clearOtpError === "function") {
                    clearOtpError();
                }
            }
        });

        // Keyboard support (Enter / Space)
        resendTimerEl.addEventListener("keydown", (e) => {
            if ((e.key === "Enter" || e.key === " ") && resendTimerEl.classList.contains("is-clickable")) {
                e.preventDefault();
                resendTimerEl.click();
            }
        });

        // Initialize 60s timer on page load
        startResendTimer(60);
    }

    // --- Verify Email OTP Input Validation ---
    if (otpInputs && otpInputs.length > 0) {
        const otpForm = otpInputs[0].closest("form");
        const otpRow = document.querySelector(".auth-otp-row");
        const otpErrorEl = document.getElementById("otpError");

        function showOtpError(message) {
            if (otpRow) otpRow.classList.add("auth-otp-row--error");
            otpInputs.forEach((input) => {
                if (!input.value.trim()) {
                    input.classList.add("auth-otp-input--error");
                }
                input.setAttribute("aria-invalid", "true");
            });
            if (otpErrorEl) {
                otpErrorEl.textContent = message;
                otpErrorEl.classList.add("is-visible");
            }
        }

        function clearOtpError() {
            if (otpRow) otpRow.classList.remove("auth-otp-row--error");
            otpInputs.forEach((input) => {
                input.classList.remove("auth-otp-input--error");
                input.removeAttribute("aria-invalid");
            });
            if (otpErrorEl) {
                otpErrorEl.textContent = "";
                otpErrorEl.classList.remove("is-visible");
            }
        }

        function validateOTP(showIfEmpty = false) {
            const entered = Array.from(otpInputs).map((inp) => inp.value.trim()).join("");

            if (!entered) {
                if (showIfEmpty) {
                    showOtpError("Please enter your 5-digit verification code.");
                    return false;
                }
                clearOtpError();
                return false;
            }

            if (entered.length < otpInputs.length) {
                if (showIfEmpty) {
                    showOtpError(`Please enter all ${otpInputs.length} digits.`);
                    return false;
                }
                return false;
            }

            clearOtpError();
            return true;
        }

        // Clear error dynamically as the user corrects their input
        otpInputs.forEach((input) => {
            input.addEventListener("input", () => {
                input.classList.remove("auth-otp-input--error");
                if (otpRow && otpRow.classList.contains("auth-otp-row--error")) {
                    const filledCount = Array.from(otpInputs).filter((inp) => inp.value.trim().length > 0).length;
                    if (filledCount === otpInputs.length) {
                        clearOtpError();
                    } else if (otpErrorEl) {
                        otpErrorEl.classList.remove("is-visible");
                        otpErrorEl.textContent = "";
                    }
                }
            });
        });

        function hasRegisteredLabs(email) {
            if (!email) return false;
            const normalized = email.toLowerCase().trim();

            // Override via URL param ?hasLabs=true or ?hasLabs=false
            const searchParams = new URLSearchParams(window.location.search);
            if (searchParams.get("hasLabs") === "true") return true;
            if (searchParams.get("hasLabs") === "false") return false;

            // Known accounts with pre-registered labs
            const registeredAccounts = [
                "rajesh@meridianlabs.in",
                "sentinel@pharmalabs.com",
                "info@meridianlabs.in",
                "contact@meridianlabs.in",
                "admin@meridianlabs.in"
            ];

            if (registeredAccounts.includes(normalized)) {
                return true;
            }

            // Keyword match for extracted lab company domains
            if (normalized.includes("meridian") || normalized.includes("sentinel")) {
                return true;
            }

            return false;
        }

        // Validate and route on submit
        if (otpForm) {
            otpForm.addEventListener("submit", (e) => {
                const isValid = validateOTP(true);
                if (!isValid) {
                    e.preventDefault();
                    const firstEmpty = Array.from(otpInputs).find((inp) => !inp.value.trim());
                    if (firstEmpty) {
                        firstEmpty.focus();
                    }
                    return;
                }

                e.preventDefault();
                const currentEmail = (emailParam || (targetEmailEl ? targetEmailEl.textContent : "") || "").trim();

                // Open email-verified.html ONLY if labs are registered with that email; otherwise open lab_website_detail.html
                if (hasRegisteredLabs(currentEmail)) {
                    window.location.href = `email-verified.html${currentEmail ? `?email=${encodeURIComponent(currentEmail)}` : ""}`;
                } else {
                    window.location.href = `lab_website_detail.html${currentEmail ? `?email=${encodeURIComponent(currentEmail)}` : ""}`;
                }
            });
        }
    }

    // --- Login Email Input Validation ---
    const loginForm = document.querySelector(".auth-form");
    const emailInput = document.getElementById("workEmail");
    const inputGroup = document.querySelector(".auth-input-group");
    const errorEl = document.getElementById("emailError");

    if (loginForm && emailInput && inputGroup) {
        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

        function showError(message) {
            inputGroup.classList.add("auth-input-group--error");
            if (errorEl) {
                errorEl.textContent = message;
                errorEl.classList.add("is-visible");
            }
            emailInput.setAttribute("aria-invalid", "true");
        }

        function clearError() {
            inputGroup.classList.remove("auth-input-group--error");
            if (errorEl) {
                errorEl.textContent = "";
                errorEl.classList.remove("is-visible");
            }
            emailInput.removeAttribute("aria-invalid");
        }

    //     function validateEmail(showIfEmpty = false) {
    //         const val = emailInput.value.trim();

    //         if (!val) {
    //             if (showIfEmpty) {
    //                 showError("Please enter your work email.");
    //                 return false;
    //             }
    //             clearError();
    //             return false;
    //         }

    //         if (!emailRegex.test(val)) {
    //             showError("Please enter a valid work email address (e.g. user@company.com).");
    //             return false;
    //         }

    //         clearError();
    //         return true;
    //     }

    //     // Clear error dynamically as the user corrects their input
    //     emailInput.addEventListener("input", () => {
    //         if (inputGroup.classList.contains("auth-input-group--error")) {
    //             validateEmail(false);
    //         }
    //     });

    //     // Validate on blur if a value was entered
    //     emailInput.addEventListener("blur", () => {
    //         if (emailInput.value.trim().length > 0) {
    //             validateEmail(true);
    //         }
    //     });

    //     // Validate on submit
    //     loginForm.addEventListener("submit", (e) => {
    //         const isValid = validateEmail(true);
    //         if (!isValid) {
    //             e.preventDefault();
    //             emailInput.focus();
    //         }
    //     });
    }

    // --- Laboratory Website Input Validation ---
    const websiteInput = document.getElementById("companyWebsite");
    if (websiteInput) {
        const labForm = websiteInput.closest("form");
        const labInputGroup = websiteInput.closest(".auth-input-group");
        const labErrorEl = document.getElementById("websiteError");

        const urlRegex = /^(https?:\/\/)?([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(\/.*)?$/i;

        function showLabError(message) {
            if (labInputGroup) labInputGroup.classList.add("auth-input-group--error");
            if (labErrorEl) {
                labErrorEl.textContent = message;
                labErrorEl.classList.add("is-visible");
            }
            websiteInput.setAttribute("aria-invalid", "true");
        }

        function clearLabError() {
            if (labInputGroup) labInputGroup.classList.remove("auth-input-group--error");
            if (labErrorEl) {
                labErrorEl.textContent = "";
                labErrorEl.classList.remove("is-visible");
            }
            websiteInput.removeAttribute("aria-invalid");
        }

        function validateWebsite(showIfEmpty = false) {
            let val = websiteInput.value.trim();

            if (!val) {
                if (showIfEmpty) {
                    showLabError("Please enter your company website.");
                    return false;
                }
                clearLabError();
                return false;
            }

            if (!urlRegex.test(val)) {
                showLabError("Please enter a valid website URL (e.g. https://www.company.com).");
                return false;
            }

            // Auto-prepend https:// if missing
            if (!/^https?:\/\//i.test(val)) {
                websiteInput.value = "https://" + val;
            }

            clearLabError();
            return true;
        }

        websiteInput.addEventListener("input", () => {
            if (labInputGroup && labInputGroup.classList.contains("auth-input-group--error")) {
                validateWebsite(false);
            }
        });

        websiteInput.addEventListener("blur", () => {
            if (websiteInput.value.trim().length > 0) {
                validateWebsite(true);
            }
        });

        if (labForm) {
            labForm.addEventListener("submit", (e) => {
                const isValid = validateWebsite(true);
                if (!isValid) {
                    e.preventDefault();
                    websiteInput.focus();
                }
            });
        }
    }

    // --- Dynamic Website Fetching Progress Controller ---
    const progressFill = document.querySelector(".auth-progress-fill");
    const progressPercent = document.querySelector(".auth-progress-percent");
    const progressTrack = document.querySelector(".auth-progress-track");
    const progressEta = document.querySelector(".auth-progress-eta-text");

    if (progressFill) {
        let simulationInterval = null;

        /**
         * Set progress value dynamically
         * @param {number} percent - percentage between 0 and 100
         * @param {string} [etaText] - optional ETA description (e.g. "5 Min Remaining")
         */
        function applyProgress(percent, etaText) {
            const clamped = Math.max(0, Math.min(100, Math.round(percent)));
            progressFill.style.width = `${clamped}%`;

            if (progressPercent) {
                progressPercent.textContent = `${clamped}%`;
            }
            if (progressTrack) {
                progressTrack.setAttribute("aria-valuenow", clamped);
                progressTrack.setAttribute("aria-valuetext", `${clamped}%`);
            }
            if (etaText && progressEta) {
                progressEta.textContent = etaText;
            }
        }

        // Expose globally so external scripts, APIs, or console can set progress
        window.setFetchingProgress = function(percent, etaText) {
            if (simulationInterval) {
                clearInterval(simulationInterval);
                simulationInterval = null;
            }
            applyProgress(percent, etaText);
        };

        // Check if progress or eta parameters are passed in the URL (e.g. ?progress=45&eta=7%20Min%20Remaining)
        const progressQuery = urlParams.get("progress");
        const etaQuery = urlParams.get("eta");

        if (progressQuery !== null && !isNaN(Number(progressQuery))) {
            applyProgress(Number(progressQuery), etaQuery || undefined);
        } else {
            // Live progressive simulation
            let currentVal = 0;
            applyProgress(currentVal, "10 Min Remaining");

            simulationInterval = setInterval(() => {
                if (currentVal < 100) {
                    const step = Math.floor(Math.random() * 8) + 5;
                    currentVal = Math.min(100, currentVal + step);
                    const remainingMin = Math.max(0, Math.round((100 - currentVal) / 10));
                    applyProgress(currentVal, currentVal === 100 ? "Complete" : `${remainingMin || 1} Min Remaining`);

                    if (currentVal === 100) {
                        clearInterval(simulationInterval);
                        simulationInterval = null;
                        setTimeout(() => {
                            const emailParamVal = new URLSearchParams(window.location.search).get("email");
                            window.location.href = emailParamVal ? `review-details.html?email=${encodeURIComponent(emailParamVal)}` : "review-details.html";
                        }, 800);
                    }
                }
            }, 800);
        }
    }

    /* ==========================================================================
       Email Verified / Facility Claim Management
       ========================================================================== */
    const verifiedContainer = document.querySelector(".verified-container");
    if (verifiedContainer) {


        // Setup trash action and inline confirmation for a facility card
        function bindFacilityCardEvents(card) {
            const trashBtn = card.querySelector(".facility-card__trash-btn");
            const confirmBox = card.querySelector(".facility-card__confirm-box");
            const cancelBtn = card.querySelector(".facility-card__confirm-btn--cancel");
            const removeBtn = card.querySelector(".facility-card__confirm-btn--remove");
            const branchId = card.getAttribute("data-branch-id");
            const actionInput = document.getElementById(`action_branch_${branchId}`);

            if (trashBtn && confirmBox) {
                // Show inline confirmation on trash click
                trashBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    trashBtn.style.display = "none";
                    confirmBox.classList.add("is-active");
                    card.classList.add("facility-card--confirming");
                });

                // Cancel confirmation
                if (cancelBtn) {
                    cancelBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        confirmBox.classList.remove("is-active");
                        trashBtn.style.display = "flex";
                        card.classList.remove("facility-card--confirming");
                    });
                }

                // Confirm removal
                if (removeBtn) {
                    removeBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        if (actionInput) {
                            actionInput.value = "unlink";
                        }
                        card.setAttribute("data-removed", "true");
                        card.style.transition = "opacity 0.2s ease, max-height 0.3s ease, margin 0.3s ease, padding 0.3s ease";
                        card.style.opacity = "0";
                        setTimeout(() => {
                            card.style.display = "none";
                        }, 250);
                    });
                }
            }
        }

        const facilityCards = verifiedContainer.querySelectorAll(".facility-card");
        facilityCards.forEach(bindFacilityCardEvents);

        // Facility Image Lightbox / Modal Slider logic
        const imageModal = document.getElementById("facilityImageModal");
        const sliderViewport = document.getElementById("facilityModalSliderViewport");
        const modalTrack = document.getElementById("facilityModalTrack");
        const modalTitle = document.getElementById("facilityImageModalTitle");
        const modalBackdrop = document.getElementById("facilityImageModalBackdrop");
        const btnCloseModal = document.getElementById("btnCloseImageModal");
        const modalNav = document.getElementById("facilityModalNav");
        const btnSliderPrev = document.getElementById("btnSliderPrev");
        const btnSliderNext = document.getElementById("btnSliderNext");
        const modalDots = document.getElementById("facilityModalDots");

        let currentImages = [];
        let currentSlideIndex = 0;

        function goToSlide(index) {
            if (!currentImages.length) return;
            if (index < 0) {
                currentSlideIndex = currentImages.length - 1;
            } else if (index >= currentImages.length) {
                currentSlideIndex = 0;
            } else {
                currentSlideIndex = index;
            }

            if (modalTrack) {
                modalTrack.style.transition = "transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)";
                modalTrack.style.transform = `translateX(-${currentSlideIndex * 100}%)`;
            }

            if (modalDots) {
                const dots = modalDots.querySelectorAll(".facility-image-modal__dot");
                dots.forEach((dot, i) => {
                    if (i === currentSlideIndex) {
                        dot.classList.add("is-active");
                        dot.setAttribute("aria-selected", "true");
                    } else {
                        dot.classList.remove("is-active");
                        dot.setAttribute("aria-selected", "false");
                    }
                });
            }
        }

        function openImageModal(images, titleText) {
            if (!imageModal || !modalTrack) return;

            currentImages = Array.isArray(images) ? images : [images];
            currentSlideIndex = 0;

            modalTrack.innerHTML = currentImages
                .map((src, i) => `
                    <div class="facility-image-modal__slide" role="group" aria-roledescription="slide" aria-label="${i + 1} of ${currentImages.length}">
                        <img src="${src}" alt="${titleText || 'Facility image'} - ${i + 1}" class="facility-image-modal__slide-img">
                    </div>
                `)
                .join("");

            const hasMultiple = currentImages.length > 1;
            if (modalDots) {
                modalDots.classList.toggle("is-hidden", !hasMultiple);
                modalDots.innerHTML = currentImages
                    .map((_, i) => `<button type="button" class="facility-image-modal__dot ${i === 0 ? 'is-active' : ''}" data-index="${i}" aria-label="Slide ${i + 1}" role="tab" aria-selected="${i === 0 ? 'true' : 'false'}"></button>`)
                    .join("");

                modalDots.querySelectorAll(".facility-image-modal__dot").forEach((dot) => {
                    dot.addEventListener("click", () => {
                        goToSlide(parseInt(dot.getAttribute("data-index"), 10));
                    });
                });
            }

            if (modalNav) modalNav.classList.toggle("is-hidden", !hasMultiple);
            if (btnSliderPrev) btnSliderPrev.classList.toggle("is-hidden", !hasMultiple);
            if (btnSliderNext) btnSliderNext.classList.toggle("is-hidden", !hasMultiple);
            if (modalTitle) modalTitle.textContent = titleText || "";

            goToSlide(0);
            imageModal.classList.add("is-open");
            imageModal.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
        }

        function closeImageModal() {
            if (!imageModal) return;
            imageModal.classList.remove("is-open");
            imageModal.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";
        }

        // Swipe & drag handling
        let isDragging = false;
        let startX = 0;
        let diffX = 0;

        function getClientX(e) {
            return e.type.includes("mouse") ? e.pageX : (e.touches && e.touches.length > 0 ? e.touches[0].clientX : 0);
        }

        function handleDragStart(e) {
            if (currentImages.length <= 1) return;
            isDragging = true;
            startX = getClientX(e);
            diffX = 0;
            if (modalTrack) modalTrack.style.transition = "none";
            if (sliderViewport) sliderViewport.classList.add("is-dragging");
        }

        function handleDragMove(e) {
            if (!isDragging) return;
            diffX = getClientX(e) - startX;
            if (modalTrack && sliderViewport) {
                const viewportWidth = sliderViewport.offsetWidth || 1;
                const currentOffset = -currentSlideIndex * viewportWidth + diffX;
                modalTrack.style.transform = `translateX(${currentOffset}px)`;
            }
        }

        function handleDragEnd() {
            if (!isDragging) return;
            isDragging = false;
            if (sliderViewport) sliderViewport.classList.remove("is-dragging");
            if (modalTrack) modalTrack.style.transition = "transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)";

            const threshold = 40;
            if (diffX < -threshold) {
                goToSlide(currentSlideIndex + 1);
            } else if (diffX > threshold) {
                goToSlide(currentSlideIndex - 1);
            } else {
                goToSlide(currentSlideIndex);
            }
            diffX = 0;
        }

        if (sliderViewport) {
            sliderViewport.addEventListener("mousedown", handleDragStart);
            window.addEventListener("mousemove", handleDragMove);
            window.addEventListener("mouseup", handleDragEnd);

            sliderViewport.addEventListener("touchstart", handleDragStart, { passive: true });
            sliderViewport.addEventListener("touchmove", handleDragMove, { passive: true });
            sliderViewport.addEventListener("touchend", handleDragEnd);
            sliderViewport.addEventListener("touchcancel", handleDragEnd);
        }

        if (imageModal) {
            if (modalBackdrop) modalBackdrop.addEventListener("click", closeImageModal);
            if (btnCloseModal) btnCloseModal.addEventListener("click", closeImageModal);
            if (btnSliderPrev) {
                btnSliderPrev.addEventListener("click", (e) => {
                    e.stopPropagation();
                    goToSlide(currentSlideIndex - 1);
                });
            }
            if (btnSliderNext) {
                btnSliderNext.addEventListener("click", (e) => {
                    e.stopPropagation();
                    goToSlide(currentSlideIndex + 1);
                });
            }
            document.addEventListener("keydown", (e) => {
                if (!imageModal.classList.contains("is-open")) return;
                if (e.key === "Escape") closeImageModal();
                else if (e.key === "ArrowLeft") goToSlide(currentSlideIndex - 1);
                else if (e.key === "ArrowRight") goToSlide(currentSlideIndex + 1);
            });
        }

        // Attach image preview triggers to thumbnail wraps
        const imgWraps = verifiedContainer.querySelectorAll(".facility-card__img-wrap[data-images]");
        imgWraps.forEach((wrap) => {
            function handlePreview(e) {
                e.stopPropagation();
                const img = wrap.querySelector(".facility-card__img");
                const card = wrap.closest(".facility-card");
                const cardTitle = card ? card.querySelector(".facility-card__name") : null;
                const titleText = cardTitle ? cardTitle.textContent.trim() : (img ? img.alt : "");

                const dataImagesAttr = wrap.getAttribute("data-images");
                if (dataImagesAttr) {
                    const imagesList = dataImagesAttr.split(",").map((s) => s.trim()).filter(Boolean);
                    if (imagesList.length > 0) {
                        openImageModal(imagesList, titleText);
                    }
                }
            }

            wrap.addEventListener("click", handlePreview);
            wrap.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handlePreview(e);
                }
            });
        });

    }
});