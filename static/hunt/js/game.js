const code = JSON.parse(document.getElementById("game-code").textContent);
const currentPlayerId = JSON.parse(document.getElementById("player-id").textContent);
getPlayerIdentity();
const statusEl = document.getElementById("status");
const countdownEl = document.getElementById("countdown");
const caughtBanner = document.getElementById("caught-banner");
const playersList = document.getElementById("players");
const caughtLog = document.getElementById("caught-log");
const snapshotPanel = document.getElementById("snapshot-panel");
const snapshotsList = document.getElementById("snapshots");
const geoStatus = document.getElementById("geo-status");
const enableLocationButton = document.getElementById("enable-location");
const caughtButton = document.getElementById("caught-button");
const stopForm = document.getElementById("stop-form");
const stopButton = document.getElementById("stop-game");
const map = L.map("map").setView([52.1, 5.2], 8);
const markers = new Map();
let ownMarker = null;
let ownName = "Jij";
let latestState = null;
let watchId = null;
let latestSnapshotSignature = "";
let latestFittedSnapshotSignature = "";
let seenCaughtIds = new Set();
let caughtBannerTimer = null;
const locationStorageKey = `hunt_location_enabled_${code}`;

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

function labeledIcon(name, className) {
  return L.divIcon({
    className: `map-label ${className}`,
    html: `<span>${name}</span><i></i>`,
    iconSize: [92, 40],
    iconAnchor: [46, 36],
    popupAnchor: [0, -34],
  });
}

function spreadSnapshots(snapshots) {
  const groups = new Map();
  (snapshots || []).forEach((snapshot) => {
    const groupKey = `${snapshot.latitude.toFixed(4)},${snapshot.longitude.toFixed(4)}`;
    if (!groups.has(groupKey)) groups.set(groupKey, []);
    groups.get(groupKey).push(snapshot);
  });

  const spread = [];
  groups.forEach((group) => {
    if (group.length === 1) {
      spread.push({ snapshot: group[0], latlng: [group[0].latitude, group[0].longitude] });
      return;
    }
    const radius = 0.00008;
    group.forEach((snapshot, index) => {
      const angle = (Math.PI * 2 * index) / group.length;
      spread.push({
        snapshot,
        latlng: [
          snapshot.latitude + Math.sin(angle) * radius,
          snapshot.longitude + Math.cos(angle) * radius,
        ],
      });
    });
  });
  return spread;
}

function markerForSnapshot(snapshot, latlng) {
  const key = `fugitive-${snapshot.player_id}`;
  const text = `${snapshot.player_name}<br>${new Date(snapshot.released_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  if (!markers.has(key)) {
    markers.set(key, L.marker(latlng, { icon: labeledIcon(snapshot.player_name, "fugitive-label") }).addTo(map));
  }
  markers.get(key)
    .setLatLng(latlng)
    .setIcon(labeledIcon(snapshot.player_name, "fugitive-label"))
    .bindPopup(text);
}

function syncSnapshotMarkers(snapshots) {
  const signature = snapshotSignature(snapshots || []);
  const activeKeys = new Set((snapshots || []).map((s) => `fugitive-${s.player_id}`));
  markers.forEach((marker, key) => {
    if (!activeKeys.has(key)) {
      map.removeLayer(marker);
      markers.delete(key);
    }
  });
  const visibleSnapshots = spreadSnapshots(snapshots || []);
  visibleSnapshots.forEach((item) => markerForSnapshot(item.snapshot, item.latlng));
  if (visibleSnapshots.length && signature && signature !== latestFittedSnapshotSignature) {
    const bounds = L.latLngBounds(visibleSnapshots.map((item) => item.latlng));
    if (ownMarker) bounds.extend(ownMarker.getLatLng());
    map.fitBounds(bounds, { padding: [36, 36], maxZoom: 16 });
    latestFittedSnapshotSignature = signature;
  }
}

function vibrate(pattern = 80) {
  if ("vibrate" in navigator) {
    navigator.vibrate(pattern);
  }
}

function snapshotSignature(snapshots) {
  return (snapshots || [])
    .map((snapshot) => `${snapshot.player_id}:${snapshot.released_at}`)
    .sort()
    .join("|");
}

function renderSnapshots(snapshots) {
  const visible = Boolean(snapshots && snapshots.length);
  const signature = snapshotSignature(snapshots || []);
  if (latestSnapshotSignature && signature && signature !== latestSnapshotSignature) {
    vibrate([80, 40, 80]);
  }
  latestSnapshotSignature = signature;
  snapshotPanel.classList.toggle("hidden", !visible);
  snapshotsList.innerHTML = "";
  (snapshots || []).forEach((snapshot) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = snapshot.player_name;
    const time = document.createElement("span");
    time.className = "badge fugitive";
    time.textContent = new Date(snapshot.released_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    item.append(name, time);
    snapshotsList.appendChild(item);
  });
}

function renderCaughtLog(caughtPlayers) {
  caughtLog.innerHTML = "";
  if (!caughtPlayers || !caughtPlayers.length) {
    const item = document.createElement("li");
    item.className = "empty-log";
    item.textContent = "Nog niemand gepakt.";
    caughtLog.appendChild(item);
    return;
  }
  caughtPlayers.forEach((player) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = player.name;
    const time = document.createElement("span");
    time.className = "badge runner";
    time.textContent = player.caught_at
      ? new Date(player.caught_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "runner";
    item.append(name, time);
    caughtLog.appendChild(item);
  });
}

function showCaughtBanner(player) {
  caughtBanner.textContent = `${player.name} is gepakt`;
  caughtBanner.classList.remove("hidden");
  requestAnimationFrame(() => caughtBanner.classList.add("show"));
  if (caughtBannerTimer) {
    clearTimeout(caughtBannerTimer);
  }
  caughtBannerTimer = setTimeout(() => {
    caughtBanner.classList.remove("show");
    setTimeout(() => caughtBanner.classList.add("hidden"), 260);
  }, 3500);
}

function notifyNewCaughtPlayers(caughtPlayers) {
  const currentIds = new Set((caughtPlayers || []).map((player) => player.id));
  (caughtPlayers || []).forEach((player) => {
    if (!seenCaughtIds.has(player.id) && player.id !== currentPlayerId) {
      showCaughtBanner(player);
      vibrate([120, 60, 120]);
    }
  });
  seenCaughtIds = currentIds;
}

function statusText(status) {
  return {
    grace_period: "Voorsprong loopt",
    active: "Jacht geopend",
    finished: "Spel afgelopen",
    lobby: "Lobby",
  }[status] || status;
}

function formatRemaining(targetIso) {
  const remaining = Math.max(0, Math.ceil((new Date(targetIso) - new Date()) / 1000));
  const minutes = String(Math.floor(remaining / 60)).padStart(2, "0");
  const seconds = String(remaining % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function updateCountdown() {
  if (!latestState) {
    countdownEl.textContent = "";
    return;
  }
  if (latestState.status === "grace_period" && latestState.active_at) {
    countdownEl.innerHTML = `<span>Voorsprong</span><strong>${formatRemaining(latestState.active_at)}</strong>`;
    return;
  }
  if (latestState.status === "active" && latestState.next_snapshot_at) {
    countdownEl.innerHTML = `<span>Volgende locatie</span><strong>${formatRemaining(latestState.next_snapshot_at)}</strong>`;
    return;
  }
  countdownEl.textContent = "";
}

function applyState(state) {
  latestState = state;
  if (state.status === "lobby") {
    window.location.href = withIdentity(`/g/${code}/lobby/`);
    return;
  }
  statusEl.textContent = statusText(state.status);
  renderPlayers(playersList, state.players);
  const current = state.players.find((player) => player.id === currentPlayerId);
  ownName = current ? current.name : "Jij";
  caughtButton.classList.toggle("hidden", !current || current.role !== "fugitive" || state.status === "finished");
  syncSnapshotMarkers(state.snapshots || []);
  renderSnapshots(state.snapshots || []);
  renderCaughtLog(state.caught_players || []);
  notifyNewCaughtPlayers(state.caught_players || []);
  updateCountdown();
}

function updateOwnLocation(position) {
  const latlng = [position.coords.latitude, position.coords.longitude];
  if (!ownMarker) {
    ownMarker = L.marker(latlng, { icon: labeledIcon(ownName, "own-label") }).addTo(map).bindPopup("Jij");
    map.setView(latlng, 15);
  } else {
    ownMarker.setLatLng(latlng).setIcon(labeledIcon(ownName, "own-label"));
  }
}

async function sendLocation(position) {
  updateOwnLocation(position);
  geoStatus.textContent = "Locatie gevonden, opslaan...";
  const csrfToken = getCookie("csrftoken");
  if (!csrfToken) {
    throw new Error("Beveiligingscookie ontbreekt. Refresh de pagina met Ctrl+F5 en probeer opnieuw.");
  }
  const response = await fetch(`/g/${code}/location/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
      ...identityHeaders(),
    },
    body: JSON.stringify({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
    }),
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (error) {
    if (response.status === 403) {
      throw new Error("Locatie is geweigerd door CSRF-beveiliging. Refresh de pagina met Ctrl+F5 en probeer opnieuw.");
    }
    throw new Error("Server gaf geen geldige locatie-response terug.");
  }
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "Locatie is niet opgeslagen door de server.");
  }
  vibrate(60);
  geoStatus.textContent = `Locatie gedeeld. Laatste update: ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function geolocationError(error) {
  const messages = {
    1: "Locatiepermissie is geweigerd. Zet locatie aan in je browserinstellingen en probeer opnieuw.",
    2: "Je locatie is nu niet beschikbaar. Controleer GPS/wifi en probeer opnieuw.",
    3: "Locatie ophalen duurde te lang. Probeer opnieuw.",
  };
  geoStatus.textContent = messages[error.code] || "Locatie kon niet worden gestart.";
  enableLocationButton.disabled = false;
  enableLocationButton.textContent = "Opnieuw proberen";
  watchId = null;
}

function startLocationSharing() {
  if (!("geolocation" in navigator)) {
    geoStatus.textContent = "Deze browser ondersteunt geen geolocation.";
    return;
  }
  if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    geoStatus.textContent = "Deze browser kan locatie op een http-netwerkadres blokkeren. Ik probeer het alsnog; werkt het niet, gebruik HTTPS of zet dit adres tijdelijk als veilige test-origin in je browser.";
  }
  if (watchId !== null) {
    return;
  }
  enableLocationButton.disabled = true;
  enableLocationButton.textContent = "Locatie actief";
  geoStatus.textContent = "Wacht op toestemming van je browser...";
  navigator.geolocation.getCurrentPosition((position) => {
    sendLocation(position).catch((error) => {
      geoStatus.textContent = error.message;
      enableLocationButton.disabled = false;
      enableLocationButton.textContent = "Opnieuw proberen";
      watchId = null;
    });
  }, geolocationError, {
    enableHighAccuracy: true,
    maximumAge: 0,
    timeout: 15000,
  });
  watchId = navigator.geolocation.watchPosition((position) => {
    sendLocation(position).catch((error) => {
      geoStatus.textContent = error.message;
    });
  }, geolocationError, {
    enableHighAccuracy: true,
    maximumAge: 5000,
    timeout: 15000,
  });
}

enableLocationButton.addEventListener("click", startLocationSharing);

if (localStorage.getItem(locationStorageKey) === "1" || localStorage.getItem("hunt_location_enabled") === "1") {
  geoStatus.textContent = "Locatie delen staat aan vanuit de lobby. Updates worden gestart...";
  startLocationSharing();
}

caughtButton.addEventListener("click", async () => {
  const response = await fetch(caughtButton.dataset.url, {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken"), ...identityHeaders() },
  });
  const data = await response.json();
  if (response.ok) applyState(data);
});

if (stopForm) {
  stopForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    stopButton.disabled = true;
    stopButton.textContent = "Stoppen...";
    const response = await fetch(stopForm.action, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
        ...identityHeaders(),
      },
      body: new FormData(stopForm),
    });
    const data = await response.json();
    if (response.ok) {
      window.location.href = data.redirect || withIdentity(`/g/${code}/lobby/`);
      return;
    }
    stopButton.disabled = false;
    stopButton.textContent = "Stop spel";
  });
}

try {
  openGameSocket(code, applyState);
} catch (error) {
  setInterval(async () => {
    const response = await fetch(withIdentity(`/g/${code}/state/`), { headers: identityHeaders() });
    applyState(await response.json());
  }, 3000);
}

setInterval(updateCountdown, 1000);
setInterval(async () => {
  const response = await fetch(withIdentity(`/g/${code}/state/`), { headers: identityHeaders() });
  if (response.ok) applyState(await response.json());
}, 5000);
