document.addEventListener('DOMContentLoaded', () => {
    /* ==========================================================================
       Header Navigation (Mobile Drawer & Backdrop)
       ========================================================================== */
    const headerToggle = document.getElementById('headerToggle');
    const headerNav = document.getElementById('headerNav');
    const headerBackdrop = document.getElementById('headerBackdrop');

    function toggleMenu(open) {
        const shouldOpen = open !== undefined ? open : !headerNav.classList.contains('active');
        headerToggle.classList.toggle('active', shouldOpen);
        headerNav.classList.toggle('active', shouldOpen);
        if (headerBackdrop) headerBackdrop.classList.toggle('active', shouldOpen);
        headerToggle.setAttribute('aria-expanded', shouldOpen);
        document.body.style.overflow = shouldOpen ? 'hidden' : '';
    }

    if (headerToggle && headerNav && !headerToggle.dataset.hdrBound) {
        headerToggle.dataset.hdrBound = 'true';
        headerToggle.addEventListener('click', () => toggleMenu());

        const headerClose = document.getElementById('headerClose');
        if (headerClose) headerClose.addEventListener('click', () => toggleMenu(false));
        if (headerBackdrop) headerBackdrop.addEventListener('click', () => toggleMenu(false));

        headerNav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => toggleMenu(false));
        });
    }

    /* ==========================================================================
       Category Tabs (Drag & Switch)
       ========================================================================== */
    const tabsBox = document.querySelector('.category-tabs');
    if (tabsBox) {
        let isDown = false, startX, scrollLeft, moved = false;

        tabsBox.addEventListener('mousedown', e => {
            isDown = true;
            moved = false;
            tabsBox.classList.add('is-dragging');
            startX = e.pageX - tabsBox.offsetLeft;
            scrollLeft = tabsBox.scrollLeft;
        });

        window.addEventListener('mousemove', e => {
            if (!isDown) return;
            const walk = e.pageX - tabsBox.offsetLeft - startX;
            if (Math.abs(walk) > 5) moved = true;
            tabsBox.scrollLeft = scrollLeft - walk;
        });

        window.addEventListener('mouseup', () => {
            isDown = false;
            tabsBox.classList.remove('is-dragging');
        });

        tabsBox.addEventListener('click', e => {
            const tab = e.target.closest('.category-tab');
            if (!tab || moved) return;
            tabsBox.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        });
    }

    /* ==========================================================================
       Top Rated Labs Carousel (Navigation & Drag)
       ========================================================================== */
    const topLabsCarousel = document.getElementById('topLabsCarousel');
    const topLabsPrev = document.getElementById('topLabsPrev');
    const topLabsNext = document.getElementById('topLabsNext');

    if (topLabsCarousel) {
        let isDown = false, startX, scrollLeft, moved = false;

        const updateArrows = () => {
            if (!topLabsPrev || !topLabsNext) return;
            const maxScroll = topLabsCarousel.scrollWidth - topLabsCarousel.clientWidth;
            topLabsPrev.disabled = topLabsCarousel.scrollLeft <= 5;
            topLabsNext.disabled = topLabsCarousel.scrollLeft >= maxScroll - 5;
        };

        const getScrollDistance = () => {
            const card = topLabsCarousel.querySelector('.lab-card');
            return card ? card.offsetWidth + 20 : 325;
        };

        if (topLabsPrev && topLabsNext) {
            topLabsPrev.addEventListener('click', () => {
                topLabsCarousel.scrollBy({ left: -getScrollDistance(), behavior: 'smooth' });
            });
            topLabsNext.addEventListener('click', () => {
                topLabsCarousel.scrollBy({ left: getScrollDistance(), behavior: 'smooth' });
            });
        }

        topLabsCarousel.addEventListener('mousedown', e => {
            isDown = true;
            moved = false;
            topLabsCarousel.classList.add('is-dragging');
            startX = e.pageX - topLabsCarousel.offsetLeft;
            scrollLeft = topLabsCarousel.scrollLeft;
        });

        window.addEventListener('mousemove', e => {
            if (!isDown) return;
            const walk = e.pageX - topLabsCarousel.offsetLeft - startX;
            if (Math.abs(walk) > 5) moved = true;
            topLabsCarousel.scrollLeft = scrollLeft - walk;
        });

        window.addEventListener('mouseup', () => {
            if (isDown) {
                isDown = false;
                topLabsCarousel.classList.remove('is-dragging');
            }
        });

        topLabsCarousel.addEventListener('click', e => {
            if (moved) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);

        topLabsCarousel.addEventListener('dragstart', e => e.preventDefault());
        topLabsCarousel.addEventListener('scroll', updateArrows, { passive: true });
        window.addEventListener('resize', updateArrows);
        updateArrows();
    }

    /* ==========================================================================
       Hero Search Testing Dropdown Interactions
       ========================================================================== */
    /*
    const testingField = document.getElementById('searchFieldTesting');

    if (testingField) {
        const list = testingField.querySelector('.hero__dropdown-list');
        const valueDisplay = document.getElementById('searchTestingValue');
        const subDisplay = testingField.querySelector('.hero__search-sub');

        let activeIndex = -1;

        const getItems = () => list ? Array.from(list.querySelectorAll('.hero__dropdown-item')) : [];

        const setActiveItem = (index) => {
            const items = getItems();
            items.forEach(item => item.classList.remove('is-active'));

            if (index >= 0 && index < items.length) {
                activeIndex = index;
                items[activeIndex].classList.add('is-active');
                items[activeIndex].scrollIntoView({ block: 'nearest' });
            } else {
                activeIndex = -1;
            }
        };

        const closeDropdown = () => {
            testingField.classList.remove('is-open');
            testingField.setAttribute('aria-expanded', 'false');
            getItems().forEach(el => el.classList.remove('is-active'));
        };

        const selectItem = (item) => {
            if (!item) return;
            const val = item.getAttribute('data-value') || item.querySelector('.hero__dropdown-item-title')?.textContent.trim();
            const desc = item.querySelector('.hero__dropdown-item-desc')?.textContent.trim();

            if (val && valueDisplay) valueDisplay.textContent = val;
            if (desc && subDisplay) subDisplay.textContent = desc;

            closeDropdown();
        };

        // Toggle dropdown on field click
        testingField.addEventListener('click', (e) => {
            if (e.target.closest('.hero__dropdown')) return;
            const isOpen = testingField.classList.contains('is-open');
            if (isOpen) {
                closeDropdown();
            } else {
                activeIndex = -1;
                testingField.classList.add('is-open');
                testingField.setAttribute('aria-expanded', 'true');
            }
        });

        // Keyboard navigation
        testingField.addEventListener('keydown', (e) => {
            const items = getItems();
            if (!testingField.classList.contains('is-open')) {
                if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    testingField.click();
                }
            } else {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (items.length === 0) return;
                    setActiveItem(activeIndex < items.length - 1 ? activeIndex + 1 : 0);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (items.length === 0) return;
                    setActiveItem(activeIndex > 0 ? activeIndex - 1 : items.length - 1);
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (activeIndex >= 0 && items[activeIndex]) {
                        selectItem(items[activeIndex]);
                    }
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    closeDropdown();
                }
            }
        });

        // Item selection & hover
        if (list) {
            list.addEventListener('mousemove', (e) => {
                const item = e.target.closest('.hero__dropdown-item');
                if (!item) return;
                const items = getItems();
                const idx = items.indexOf(item);
                if (idx !== -1 && idx !== activeIndex) {
                    items.forEach(el => el.classList.remove('is-active'));
                    activeIndex = idx;
                    item.classList.add('is-active');
                }
            });

            list.addEventListener('click', (e) => {
                const item = e.target.closest('.hero__dropdown-item');
                if (!item) return;
                selectItem(item);
            });
        }

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#searchFieldTesting')) {
                closeDropdown();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeDropdown();
            }
        });
    }
    */

    /* ==========================================================================
       Hero Search Tabs (Drag to Scroll)
       ========================================================================== */
    const heroSearchTabs = document.querySelector('.hero__search-tabs');
    if (heroSearchTabs) {
        let isDown = false;
        let startX = 0;
        let scrollLeft = 0;
        let hasMoved = false;

        heroSearchTabs.addEventListener('mousedown', (e) => {
            // Only track drag on the tabs container, not when starting on a button press intent
            isDown = true;
            hasMoved = false;
            startX = e.pageX - heroSearchTabs.offsetLeft;
            scrollLeft = heroSearchTabs.scrollLeft;
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            const x = e.pageX - heroSearchTabs.offsetLeft;
            const walk = (x - startX) * 1.5;
            if (Math.abs(x - startX) > 6) {
                hasMoved = true;
                heroSearchTabs.classList.add('is-dragging');
            }
            if (hasMoved) {
                heroSearchTabs.scrollLeft = scrollLeft - walk;
            }
        });

        window.addEventListener('mouseup', () => {
            if (!isDown) return;
            isDown = false;
            heroSearchTabs.classList.remove('is-dragging');
            // keep hasMoved until after click event in same gesture
            setTimeout(() => { hasMoved = false; }, 0);
        });

        // Only block click if user actually dragged
        heroSearchTabs.addEventListener('click', (e) => {
            if (hasMoved) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        }, true);

        heroSearchTabs.addEventListener('wheel', (e) => {
            if (Math.abs(e.deltaX) === 0 && Math.abs(e.deltaY) > 0) {
                if (heroSearchTabs.scrollWidth > heroSearchTabs.clientWidth) {
                    heroSearchTabs.scrollLeft += e.deltaY;
                    e.preventDefault();
                }
            }
        }, { passive: false });
    }

    /* ==========================================================================
       Hero Search Inputs & Container Resizing
       ========================================================================== */
    const heroSearchBoxes = document.querySelectorAll('.hero__search-box');

    heroSearchBoxes.forEach((heroSearchBox) => {
        const heroSearchInput = heroSearchBox.querySelector('.hero__search-input');
        const heroSearchBtn = heroSearchBox.querySelector('.hero__search-btn');

        if (!heroSearchInput) return;

        let isManuallyResized = false;
        let userManualHeight = 0;

        // Detect if user manually resizes this container via its bottom-right handle
        let mousedownHeight = 0;
        heroSearchBox.addEventListener('mousedown', () => {
            mousedownHeight = heroSearchBox.offsetHeight;
            const onMouseUp = () => {
                window.removeEventListener('mouseup', onMouseUp);
                const currentHeight = heroSearchBox.offsetHeight;
                if (Math.abs(currentHeight - mousedownHeight) > 4) {
                    isManuallyResized = true;
                    userManualHeight = currentHeight;
                }
            };
            window.addEventListener('mouseup', onMouseUp);
        });

        const autoResize = () => {
            // Temporarily reset inline height to measure needed scroll height
            heroSearchInput.style.height = 'auto';
            const inputScrollHeight = heroSearchInput.scrollHeight;

            // Needed box height = input scrollHeight + label + padding clearance (~70px)
            const minBoxHeight = 100;
            const neededBoxHeight = Math.max(minBoxHeight, inputScrollHeight + 70);

            if (isManuallyResized && userManualHeight > minBoxHeight) {
                heroSearchBox.style.height = `${Math.max(userManualHeight, neededBoxHeight)}px`;
            } else if (inputScrollHeight > 32) {
                heroSearchBox.style.height = `${Math.min(450, neededBoxHeight)}px`;
            } else if (!isManuallyResized) {
                heroSearchBox.style.height = '';
            }

            heroSearchInput.style.height = '100%';
        };

        // Auto-expand on typing, pasting, or deleting text
        heroSearchInput.addEventListener('input', autoResize);

        // Reset manual resize if input is emptied
        heroSearchInput.addEventListener('input', () => {
            if (!heroSearchInput.value.trim()) {
                isManuallyResized = false;
                userManualHeight = 0;
                heroSearchBox.style.height = '';
                heroSearchInput.style.height = '100%';
            }
        });

        // Enter submits / Shift+Enter creates a new line (ChatGPT behavior)
        heroSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (heroSearchBtn) {
                    heroSearchBtn.click();
                }
            }
        });

        // Focus input when clicking anywhere inside the search box
        heroSearchBox.addEventListener('click', (e) => {
            if (!e.target.closest('.hero__search-btn') && e.target !== heroSearchInput) {
                heroSearchInput.focus();
            }
        });
    });
});