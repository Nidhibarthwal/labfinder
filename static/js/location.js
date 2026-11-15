document.addEventListener("DOMContentLoaded", function () {
    const locationBtn = document.getElementById("headerLocationBtn");
    const locationLabel = document.getElementById("headerLocationLabel");
    const modal = document.getElementById("locationModal");
    const modalClose = document.getElementById("locModalClose");
    const modalBackdrop = document.getElementById("locModalBackdrop");
    const searchInput = document.getElementById("locSearchInput");
    const searchClear = document.getElementById("locSearchClear");
    const suggestionsBox = document.getElementById("locSuggestions");
    const detectBtn = document.getElementById("locDetectBtn");

    let map = null;
    let mapMarker = null;

    // 1. Sync existing localStorage to cookies on initial page load
    function initLocation() {
        const savedCity = localStorage.getItem("user_city");
        const savedState = localStorage.getItem("user_state");

        if (savedCity) {
            // Synchronize cookie if missing
            setCookie("user_city", savedCity);
            if (savedState) setCookie("user_state", savedState);
            updateLocationUI(savedCity, savedState);
        } else {
            if (locationLabel) {
                locationLabel.textContent = "Select Location";
            }
        }
    }

    // Helper to set cookie reliably across the site
    function setCookie(name, value, days = 30) {
        const d = new Date();
        d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/`;
    }

    // 2. Set location in LocalStorage, Cookies, and trigger AJAX update
    function setLocation(city, state) {
        if (city) {
            localStorage.setItem("user_city", city);
            if (state) localStorage.setItem("user_state", state);
            
            setCookie("user_city", city);
            setCookie("user_state", state || "");

            updateLocationUI(city, state);

            // Fetch dynamic labs via AJAX endpoint
            fetchNearbyLabs(city, state);
        }
        closeModal();
    }

    // 3. Function to dynamically update labs section on the homepage
    function fetchNearbyLabs(city, state) {
        const titleElem = document.querySelector(".top-labs__title");
        if (titleElem) {
            titleElem.textContent = `Top rated labs near ${city}`;
        }

        fetch(`/api/home/top-labs/?city=${encodeURIComponent(city)}&state=${encodeURIComponent(state)}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById("topLabsContainer");
                if (container && data.html) {
                    container.innerHTML = data.html;
                }
            })
            .catch(err => console.error("Failed to load location labs:", err));
    }

    function updateLocationUI(city, state) {
        if (locationLabel) {
            locationLabel.textContent = state ? `${city}, ${state}` : city;
        }
    }

    // 4. Modal Open / Close Logic
    function openModal() {
        if (modal) {
            modal.removeAttribute("hidden");
            initMap();
        }
    }

    function closeModal() {
        if (modal) {
            modal.setAttribute("hidden", "");
        }
        if (suggestionsBox) {
            suggestionsBox.hidden = true;
        }
        if (searchInput) {
            searchInput.value = "";
        }
    }

    if (locationBtn) locationBtn.addEventListener("click", openModal);
    if (modalClose) modalClose.addEventListener("click", closeModal);
    if (modalBackdrop) modalBackdrop.addEventListener("click", closeModal);

    // 5. Leaflet Map Initialization (ArcGIS Tiles to fix 403 blocking)
    function initMap() {
        if (map) {
            setTimeout(() => map.invalidateSize(), 200);
            return;
        }

        const mapContainer = document.getElementById("locModalMap");
        if (!mapContainer) return;

        // Default map center view (India wide view)
        map = L.map("locModalMap", {
            attributionControl: false
        }).setView([20.5937, 78.9629], 5);

        // ArcGIS Tiles to replace blocked OSM tiles
        L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
            maxZoom: 19
        }).addTo(map);

        map.on("click", function (e) {
            const { lat, lng } = e.latlng;
            placeMarker(lat, lng);
            reverseGeocode(lat, lng);
        });

        setTimeout(() => map.invalidateSize(), 200);
    }

    function placeMarker(lat, lng) {
        if (mapMarker) {
            mapMarker.setLatLng([lat, lng]);
        } else {
            mapMarker = L.marker([lat, lng]).addTo(map);
        }
        map.setView([lat, lng], 12);
    }

    // 6. Reverse Geocoding via Nominatim
    function reverseGeocode(lat, lng) {
        fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.address) {
                    const city = data.address.city || data.address.town || data.address.village || data.address.state_district;
                    const state = data.address.state || "";
                    if (city) {
                        setLocation(city, state);
                    }
                }
            })
            .catch(err => console.error("Geocoding error:", err));
    }

    // 7. Detect My Location via Browser Geolocation
    if (detectBtn) {
        detectBtn.addEventListener("click", function () {
            if (navigator.geolocation) {
                detectBtn.innerText = "Detecting...";
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const { latitude, longitude } = position.coords;
                        placeMarker(latitude, longitude);
                        reverseGeocode(latitude, longitude);
                        detectBtn.innerText = "Detect my location";
                    },
                    (error) => {
                        alert("Unable to retrieve location. Please search manually.");
                        detectBtn.innerText = "Detect my location";
                    }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }

    // 8. Auto-search Location Suggestions
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            const query = searchInput.value.trim();
            if (searchClear) searchClear.hidden = query.length === 0;

            if (query.length < 3) {
                if (suggestionsBox) suggestionsBox.hidden = true;
                return;
            }

            fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&countrycodes=in&limit=5`)
                .then(res => res.json())
                .then(data => {
                    if (!suggestionsBox) return;
                    suggestionsBox.innerHTML = "";
                    if (data.length === 0) {
                        suggestionsBox.hidden = true;
                        return;
                    }

                    data.forEach(item => {
                        const btn = document.createElement("button");
                        btn.type = "button";
                        btn.className = "loc-sugg-item";
                        btn.textContent = item.display_name;
                        btn.addEventListener("click", () => {
                            const lat = parseFloat(item.lat);
                            const lon = parseFloat(item.lon);
                            placeMarker(lat, lon);
                            reverseGeocode(lat, lon);
                        });
                        suggestionsBox.appendChild(btn);
                    });
                    suggestionsBox.hidden = false;
                })
                .catch(err => console.error("Search error:", err));
        });
    }

    if (searchClear) {
        searchClear.addEventListener("click", () => {
            searchInput.value = "";
            searchClear.hidden = true;
            if (suggestionsBox) suggestionsBox.hidden = true;
        });
    }

    // Run initialization
    initLocation();
});