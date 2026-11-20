// SHEGUARD AI - Glassmorphism Interactive Safety Engine

let watchId = null;
let trackingActive = false;
let lastSentTime = 0;
const UPDATE_INTERVAL = 10000; // 10 seconds

// Web Audio API Emergency Siren/Beep Generator (Zero external assets needed)
function playEmergencySound() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(800, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15);
        osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.3);

        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.4);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
        // Audio might be blocked by browser policy until user gesture
    }
}

// Get CSRF Token from meta tag
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
}

// Helper: Post JSON data with CSRF protection
async function postData(url, data) {
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            return await response.json();
        }

        return {
            success: response.ok,
            message: response.statusText || "Server responded with status " + response.status
        };
    } catch (error) {
        console.error("Network or parse error in postData:", error);
        return {
            success: false,
            message: "Network connection error. Please verify server connection."
        };
    }
}

// Display UI Status Feedback with Glass Glow
function showStatus(elementId, text, type = "info") {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.innerHTML = text;
    el.className = `status-chip status-${type}`;
    el.style.display = "inline-flex";
}

// ================= SOS EMERGENCY TRIGGER =================
async function sendSOS() {
    const sosBtn = document.querySelector(".sos-button");
    const msgBox = document.getElementById("sos-message");

    if (sosBtn) {
        sosBtn.classList.add("sos-pulsing");
    }

    playEmergencySound();
    showStatus("sos-message", `<span class="spinner"></span> Acquiring emergency GPS coordinates...`, "info");

    const submitSOSCoordinates = async (lat, lon, note = "") => {
        try {
            const data = await postData("/sos", {
                latitude: lat,
                longitude: lon
            });

            if (data.success) {
                const mapsUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}`;
                const smsInfo = data.sms_enabled
                    ? `SMS Sent: ${data.sms_submitted} / Failed: ${data.sms_failed}`
                    : `SMS Disabled in Settings`;

                const alertHtml = `
                    <div class="sos-success-card">
                        <div class="sos-success-title">
                            <span class="beacon-dot"></span> EMERGENCY SOS RECORDED!
                        </div>
                        <div class="sos-success-details">
                            <p><strong>Alert ID:</strong> #${data.alert_id} ${note ? `(${note})` : ""}</p>
                            <p><strong>GPS Location:</strong> ${lat.toFixed(5)}, ${lon.toFixed(5)}</p>
                            <p><strong>SMS Status:</strong> ${smsInfo}</p>
                        </div>
                        <a href="${mapsUrl}" target="_blank" class="glass-btn glass-btn-sm" style="margin-top: 8px;">
                            View on Live Map &rarr;
                        </a>
                    </div>
                `;
                if (msgBox) {
                    msgBox.innerHTML = alertHtml;
                    msgBox.className = "status-box";
                    msgBox.style.display = "block";
                }

                // Update last location display dynamically on the dashboard
                const locDisplay = document.getElementById("last-location-display");
                if (locDisplay) {
                    locDisplay.innerHTML = `
                        <div class="location-badge">
                            <span>Last saved: ${lat.toFixed(5)}, ${lon.toFixed(5)}</span>
                            <a target="_blank" href="${mapsUrl}" class="glass-link">View Live Map &rarr;</a>
                        </div>
                    `;
                }

                // Increment SOS count stat badge if present
                const alertCountEl = document.getElementById("stat-alert-count");
                if (alertCountEl) {
                    const currentCount = parseInt(alertCountEl.innerText) || 0;
                    alertCountEl.innerText = currentCount + 1;
                }
            } else {
                showStatus("sos-message", data.message || "Failed to log SOS alert.", "danger");
            }
        } catch (err) {
            showStatus("sos-message", "Emergency server request failed. Please call 112 / 911 directly.", "danger");
        } finally {
            if (sosBtn) {
                setTimeout(() => sosBtn.classList.remove("sos-pulsing"), 3000);
            }
        }
    };

    if (!navigator.geolocation) {
        showStatus("sos-message", "GPS not supported by browser. Dispatching with fallback coordinates...", "warning");
        await submitSOSCoordinates(28.6139, 77.2090, "Fallback GPS");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async function (position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            await submitSOSCoordinates(lat, lon);
        },
        async function (error) {
            console.warn("High-accuracy GPS failed, trying fallback:", error.message);
            // Fallback: try approximate location or default coordinates so emergency is NEVER suppressed
            navigator.geolocation.getCurrentPosition(
                async function (lowAccPos) {
                    await submitSOSCoordinates(lowAccPos.coords.latitude, lowAccPos.coords.longitude, "Low Accuracy");
                },
                async function () {
                    // Browser completely denied location permission
                    showStatus("sos-message", "GPS Permission denied. Dispatching emergency alert with fallback location...", "warning");
                    await submitSOSCoordinates(28.6139, 77.2090, "Permission Denied Fallback");
                },
                { enableHighAccuracy: false, timeout: 5000, maximumAge: 60000 }
            );
        },
        {
            enableHighAccuracy: true,
            timeout: 8000,
            maximumAge: 0
        }
    );
}

// ================= LIVE LOCATION TRACKING =================
async function saveLocation(position) {
    const now = Date.now();
    if (now - lastSentTime < UPDATE_INTERVAL) return;
    lastSentTime = now;

    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    try {
        const data = await postData("/update-location", {
            latitude: lat,
            longitude: lon
        });

        if (data.success) {
            showStatus("location-message", `Live ping sent (${new Date().toLocaleTimeString()}): ${lat.toFixed(4)}, ${lon.toFixed(4)}`, "success");
            const locDisplay = document.getElementById("last-location-display");
            if (locDisplay) {
                locDisplay.innerHTML = `
                    <div class="location-badge">
                        <span>Last saved: ${lat.toFixed(5)}, ${lon.toFixed(5)}</span>
                        <a target="_blank" href="https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}" class="glass-link">View Live Map &rarr;</a>
                    </div>
                `;
            }
        } else {
            showStatus("location-message", data.message || "Location ping failed", "danger");
        }
    } catch (err) {
        showStatus("location-message", "Connection lost during live tracking.", "danger");
    }
}

async function startTracking() {
    if (!navigator.geolocation) {
        showStatus("location-message", "Geolocation is not supported by your browser.", "danger");
        return;
    }

    try {
        const data = await postData("/tracking-settings", { enabled: true });
        if (!data.success) throw new Error(data.message);

        trackingActive = true;
        updateTrackingUI(true);

        watchId = navigator.geolocation.watchPosition(
            saveLocation,
            function (error) {
                console.warn("watchPosition error:", error.message);
                showStatus("location-message", "Live GPS signal weak or permission required.", "warning");
            },
            {
                enableHighAccuracy: true,
                maximumAge: 5000,
                timeout: 10000
            }
        );

        showStatus("location-message", "Live location tracking active.", "success");
    } catch (error) {
        showStatus("location-message", "Could not enable tracking.", "danger");
    }
}

async function stopTracking() {
    try {
        const data = await postData("/tracking-settings", { enabled: false });
        if (!data.success) throw new Error(data.message);

        trackingActive = false;
        if (watchId !== null) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
        }

        updateTrackingUI(false);
        showStatus("location-message", "Live tracking disabled.", "info");
    } catch (error) {
        showStatus("location-message", "Could not disable tracking.", "danger");
    }
}

function updateTrackingUI(isActive) {
    const statusText = document.getElementById("tracking-status");
    const trackingBtn = document.getElementById("tracking-button");

    if (statusText) {
        statusText.innerHTML = isActive
            ? `<span class="badge-active"><span class="beacon-dot"></span> Active</span>`
            : `<span class="badge-inactive">Disabled</span>`;
    }

    if (trackingBtn) {
        trackingBtn.innerHTML = isActive
            ? `<span>&#9632; Stop Tracking</span>`
            : `<span>&#9658; Start Live Tracking</span>`;
        if (isActive) {
            trackingBtn.classList.add("btn-active-tracking");
        } else {
            trackingBtn.classList.remove("btn-active-tracking");
        }
    }
}

function toggleTracking() {
    if (trackingActive) {
        stopTracking();
    } else {
        startTracking();
    }
}

// ================= INTERACTIVE AI RISK PREDICTION =================
function setupRiskForm() {
    const form = document.getElementById("risk-prediction-form");
    if (!form) return;

    form.addEventListener("submit", async function (e) {
        // Allow form to submit via AJAX for smooth glass interaction without full reload
        e.preventDefault();
        const submitBtn = form.querySelector("button[type='submit']");
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<span class="spinner"></span> Assessing Risk with AI...`;
        }

        const formData = new FormData(form);
        const payload = {
            followed: formData.get("followed") === "yes",
            isolated: formData.get("isolated") === "yes",
            threat: formData.get("threat") === "yes",
            unsafe: formData.get("unsafe") === "yes"
        };

        try {
            const data = await postData("/risk", payload);
            if (data.success) {
                renderRiskResult(data.risk_level, data.risk_score);
            } else {
                // Fallback to standard form submit
                form.submit();
            }
        } catch (err) {
            form.submit();
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = `Predict Risk with AI`;
            }
        }
    });
}

function renderRiskResult(level, score) {
    const container = document.getElementById("risk-result-container");
    if (!container) return;

    let badgeClass = "risk-low";
    let icon = "🛡️";
    let advice = "Environment appears safe. Stay alert and aware of your surroundings.";

    if (level === "HIGH") {
        badgeClass = "risk-high";
        icon = "🚨";
        advice = "DANGER DETECTED: Move to a crowded public area, notify contacts, or press SOS immediately.";
    } else if (level === "MEDIUM") {
        badgeClass = "risk-medium";
        icon = "⚠️";
        advice = "HEIGHTENED RISK: Avoid deserted paths, share your live location, and keep your phone ready.";
    }

    container.innerHTML = `
        <div class="risk-result-card ${badgeClass}">
            <div class="risk-header">
                <span class="risk-icon">${icon}</span>
                <div>
                    <h4 class="risk-title">${level} RISK LEVEL</h4>
                    <p class="risk-score">Safety Threat Score: <strong>${score} / 100</strong></p>
                </div>
            </div>
            <div class="risk-meter-bar">
                <div class="risk-meter-fill" style="width: ${Math.min(score, 100)}%;"></div>
            </div>
            <p class="risk-advice">${advice}</p>
        </div>
    `;
    container.style.display = "block";
}

// Auto-fade flash messages after 6 seconds
function initFlashMessages() {
    const messages = document.querySelectorAll(".glass-message");
    messages.forEach((msg) => {
        setTimeout(() => {
            msg.style.opacity = "0";
            msg.style.transform = "translateY(-10px)";
            setTimeout(() => msg.remove(), 400);
        }, 5000);
    });
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", function () {
    initFlashMessages();
    setupRiskForm();

    const statusEl = document.getElementById("tracking-status");
    if (statusEl) {
        const text = statusEl.innerText.toLowerCase();
        if (text.includes("active") || text.includes("enabled")) {
            trackingActive = true;
            updateTrackingUI(true);
            if (navigator.geolocation) {
                watchId = navigator.geolocation.watchPosition(
                    saveLocation,
                    (err) => console.log("Init watchPosition:", err.message),
                    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
                );
            }
        }
    }
});
