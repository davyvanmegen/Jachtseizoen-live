const code = JSON.parse(document.getElementById("game-code").textContent);
const currentPlayerId = JSON.parse(document.getElementById("player-id").textContent);
getPlayerIdentity();
const isHost = JSON.parse(document.getElementById("is-host").textContent);
const playersList = document.getElementById("players");
const picker = document.getElementById("runner-picker");
const selectedInput = document.getElementById("start-runner-ids");
const settingsForm = document.getElementById("settings-form");
const startForm = document.getElementById("start-form");
const startButton = document.getElementById("start-game");
const randomButton = document.getElementById("random-runners");
const hostError = document.getElementById("host-error");
const hostPanel = document.getElementById("host-panel");
const locationToggle = document.getElementById("location-toggle");
const locationStatus = document.getElementById("location-status");
let latestPlayers = [];
let manualRunnerIds = new Set();
let serverSelectionLoaded = false;
let randomMode = false;
let startInProgress = false;
const locationStorageKey = `hunt_location_enabled_${code}`;

function selectedRunnerIds() {
  return Array.from(manualRunnerIds);
}

function renderPicker(players) {
  if (!picker) return;
  if (!serverSelectionLoaded && !randomMode) {
    players.filter((player) => player.is_start_runner).forEach((player) => manualRunnerIds.add(String(player.id)));
    serverSelectionLoaded = true;
  }
  picker.innerHTML = "";
  players.forEach((player) => {
    const row = document.createElement("div");
    row.className = "role-row";
    const name = document.createElement("strong");
    name.textContent = player.name + (player.id === currentPlayerId ? " (jij)" : "");
    const controls = document.createElement("div");
    controls.className = "segmented";

    const runner = document.createElement("button");
    runner.type = "button";
    runner.textContent = "runner";
    runner.className = manualRunnerIds.has(String(player.id)) ? "active" : "";
    runner.addEventListener("click", () => {
      randomMode = false;
      manualRunnerIds.add(String(player.id));
      renderPicker(latestPlayers);
      selectedInput.value = selectedRunnerIds().join(",");
    });

    const fugitive = document.createElement("button");
    fugitive.type = "button";
    fugitive.textContent = "vluchter";
    fugitive.className = manualRunnerIds.has(String(player.id)) ? "" : "active";
    fugitive.addEventListener("click", () => {
      randomMode = false;
      manualRunnerIds.delete(String(player.id));
      renderPicker(latestPlayers);
      selectedInput.value = selectedRunnerIds().join(",");
    });

    controls.append(runner, fugitive);
    row.append(name, controls);
    picker.appendChild(row);
  });
  selectedInput.value = selectedRunnerIds().join(",");
}

function applyState(state) {
  latestPlayers = state.players;
  renderPlayers(playersList, latestPlayers);
  renderPicker(latestPlayers);
  if (hostPanel && state.current_player_id === currentPlayerId && !state.is_host) {
    hostPanel.classList.add("hidden");
  }
  if (state.status !== "lobby" && !startInProgress) {
    window.location.href = withIdentity(`/g/${code}/`);
  }
}

async function postForm(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
      "X-Requested-With": "XMLHttpRequest",
      ...identityHeaders(),
    },
    body: formData,
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(text || "De server gaf geen geldige JSON terug.");
  }
  if (!response.ok) throw new Error(data.error || JSON.stringify(data.errors || data));
  return data;
}

if (isHost && settingsForm) {
  settingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hostError.textContent = "";
    if (hostPanel && hostPanel.classList.contains("hidden")) {
      hostError.textContent = "Deze browser is niet de host.";
      return;
    }
    selectedInput.value = selectedRunnerIds().join(",");
    try {
      await postForm(settingsForm.dataset.url, new FormData(settingsForm));
    } catch (error) {
      hostError.textContent = error.message;
    }
  });
}

if (isHost && startForm) {
  startForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hostError.textContent = "";
    if (hostPanel && hostPanel.classList.contains("hidden")) {
      hostError.textContent = "Deze browser is niet de host.";
      return;
    }
    startInProgress = true;
    startButton.disabled = true;
    startButton.textContent = "Starten...";
    try {
      if (settingsForm) {
        selectedInput.value = selectedRunnerIds().join(",");
        await postForm(settingsForm.dataset.url, new FormData(settingsForm));
      }
      const data = await postForm(startForm.action, new FormData(startForm));
      window.location.href = data.redirect || withIdentity(`/g/${code}/`);
    } catch (error) {
      startInProgress = false;
      startButton.disabled = false;
      startButton.textContent = "Start spel";
      hostError.textContent = error.message;
    }
  });
}

if (isHost && randomButton) {
  randomButton.addEventListener("click", () => {
    randomMode = true;
    serverSelectionLoaded = true;
    manualRunnerIds.clear();
    selectedInput.value = "";
    renderPicker(latestPlayers);
  });
}

function setLocationEnabled(enabled) {
  localStorage.setItem(locationStorageKey, enabled ? "1" : "0");
  localStorage.setItem("hunt_location_enabled", enabled ? "1" : "0");
  locationToggle.checked = enabled;
}

function setLocationStatus(text, isError = false) {
  locationStatus.textContent = text;
  locationStatus.classList.toggle("error", isError);
}

function requestLobbyLocation() {
  if (!("geolocation" in navigator)) {
    setLocationEnabled(false);
    setLocationStatus("Deze browser ondersteunt geen locatie.", true);
    return;
  }
  setLocationStatus("Wacht op toestemming van je browser...");
  navigator.geolocation.getCurrentPosition(() => {
    setLocationEnabled(true);
    setLocationStatus("Locatie delen staat aan. Tijdens het spel wordt je locatie automatisch gedeeld.");
  }, (error) => {
    setLocationEnabled(false);
    const denied = error.code === 1;
    setLocationStatus(
      denied
        ? "Locatiepermissie is geweigerd. Zet locatie toe in je browserinstellingen en probeer opnieuw."
        : "Locatie kon niet worden opgehaald. Controleer GPS/wifi en probeer opnieuw.",
      true
    );
  }, {
    enableHighAccuracy: true,
    maximumAge: 0,
    timeout: 15000,
  });
}

if (locationToggle) {
  locationToggle.checked = localStorage.getItem(locationStorageKey) === "1" || localStorage.getItem("hunt_location_enabled") === "1";
  if (locationToggle.checked) {
    setLocationStatus("Locatie delen staat aan.");
  }
  locationToggle.addEventListener("change", () => {
    if (locationToggle.checked) {
      requestLobbyLocation();
    } else {
      setLocationEnabled(false);
      setLocationStatus("Locatie delen staat uit.");
    }
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
