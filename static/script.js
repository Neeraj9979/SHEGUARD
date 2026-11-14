let watchId = null;

let trackingActive = false;

let lastSentTime = 0;

const UPDATE_INTERVAL = 15000;


// Get CSRF token
function getCSRFToken() {

    return document.querySelector(
        'meta[name="csrf-token"]'
    ).getAttribute("content");

}


// Send request to Flask
async function postData(url, data) {

    let response = await fetch(url, {

        method: "POST",

        headers: {

            "Content-Type": "application/json",

            "X-CSRFToken": getCSRFToken()

        },

        body: JSON.stringify(data)

    });

    return await response.json();

}


// SOS FUNCTION
async function sendSOS() {

    let message = document.getElementById("sos-message");

    if (!navigator.geolocation) {

        message.innerText =
            "GPS is not supported by this browser.";

        return;

    }

    message.innerText = "Getting location...";

    navigator.geolocation.getCurrentPosition(

        async function(position) {

            let latitude = position.coords.latitude;

            let longitude = position.coords.longitude;

            try {

                let data = await postData("/sos", {

                    latitude: latitude,

                    longitude: longitude

                });

                if (data.success) {

                    message.innerText =
                        "SOS recorded. SMS submissions: " +
                        data.sms_submitted +
                        ". Failed: " + data.sms_failed;

                } else {

                    message.innerText = data.message;

                }

            } catch(error) {

                message.innerText =
                    "Unable to process SOS request.";

            }

        },

        function(error) {

            message.innerText =
                "Unable to obtain GPS location. " +
                "Please enable location permission.";

        },

        {

            enableHighAccuracy: true,

            timeout: 15000,

            maximumAge: 0

        }

    );

}


// SAVE LOCATION
async function saveLocation(position) {

    let now = Date.now();

    if (now - lastSentTime < UPDATE_INTERVAL) {

        return;

    }

    lastSentTime = now;

    let latitude = position.coords.latitude;

    let longitude = position.coords.longitude;

    try {

        let data = await postData(
            "/update-location",
            {
                latitude: latitude,
                longitude: longitude
            }
        );

        if (data.success) {

            document.getElementById(
                "location-message"
            ).innerText = "Location updated successfully.";

        } else {

            document.getElementById(
                "location-message"
            ).innerText = data.message;

        }

    } catch(error) {

        document.getElementById(
            "location-message"
        ).innerText = "Location update failed.";

    }

}


// START TRACKING
async function startTracking() {

    if (!navigator.geolocation) {

        alert("Geolocation is not supported.");

        return;

    }

    try {

        let data = await postData(
            "/tracking-settings",
            { enabled: true }
        );

        if (!data.success) {

            throw new Error(data.message);

        }

        trackingActive = true;

        document.getElementById(
            "tracking-status"
        ).innerText = "Tracking enabled";

        document.getElementById(
            "tracking-button"
        ).innerText = "Stop Tracking";

        watchId = navigator.geolocation.watchPosition(

            saveLocation,

            function(error) {

                document.getElementById(
                    "location-message"
                ).innerText =
                    "GPS permission denied or unavailable.";

            },

            {

                enableHighAccuracy: true,

                maximumAge: 5000,

                timeout: 15000

            }

        );

    } catch(error) {

        alert("Unable to enable tracking.");

    }

}


// STOP TRACKING
async function stopTracking() {

    try {

        let data = await postData(
            "/tracking-settings",
            { enabled: false }
        );

        if (!data.success) {

            alert(data.message);

            return;

        }

        trackingActive = false;

        if (watchId !== null) {

            navigator.geolocation.clearWatch(watchId);

            watchId = null;

        }

        document.getElementById(
            "tracking-status"
        ).innerText = "Tracking disabled";

        document.getElementById(
            "tracking-button"
        ).innerText = "Start Live Tracking";

        document.getElementById(
            "location-message"
        ).innerText = "Location sharing stopped.";

    } catch(error) {

        alert("Unable to stop tracking.");

    }

}


// TOGGLE TRACKING
function toggleTracking() {

    if (trackingActive) {

        stopTracking();

    } else {

        startTracking();

    }

}


// Initialize tracking if it was previously enabled
document.addEventListener("DOMContentLoaded", function() {

    let status = document.getElementById("tracking-status");

    if (
        status &&
        status.innerText.trim() === "Tracking enabled"
    ) {

        startTracking();

    }

});