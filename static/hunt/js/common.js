function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function getPlayerIdentity() {
  const playerIdEl = document.getElementById("player-id");
  const playerTokenEl = document.getElementById("player-token");
  const codeEl = document.getElementById("game-code");
  if (!playerIdEl || !playerTokenEl || !codeEl) return null;
  const code = JSON.parse(codeEl.textContent);
  const playerId = JSON.parse(playerIdEl.textContent);
  const token = JSON.parse(playerTokenEl.textContent);
  sessionStorage.setItem(`hunt_player_id_${code}`, String(playerId));
  sessionStorage.setItem(`hunt_player_token_${code}`, token);
  return { code, playerId, token };
}

function identityHeaders() {
  const identity = getPlayerIdentity();
  if (!identity) return {};
  return {
    "X-Player-Id": String(identity.playerId),
    "X-Player-Token": identity.token,
  };
}

function identityQuery() {
  const identity = getPlayerIdentity();
  if (!identity) return "";
  return `player_id=${encodeURIComponent(identity.playerId)}&token=${encodeURIComponent(identity.token)}`;
}

function withIdentity(url) {
  const query = identityQuery();
  if (!query) return url;
  return `${url}${url.includes("?") ? "&" : "?"}${query}`;
}

function openGameSocket(code, onMessage) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const query = identityQuery();
  const suffix = query ? `?${query}` : "";
  const socket = new WebSocket(`${proto}://${window.location.host}/ws/game/${code}/${suffix}`);
  socket.onmessage = (event) => onMessage(JSON.parse(event.data));
  return socket;
}

function renderPlayers(target, players) {
  target.innerHTML = "";
  players.forEach((player) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = player.name + (player.is_host ? " (host)" : "");
    const role = document.createElement("span");
    role.className = `badge ${player.role === "hunter" ? "runner" : "fugitive"}`;
    role.textContent = player.role === "hunter" ? "runner" : "vluchter";
    item.append(name, role);
    target.appendChild(item);
  });
}
