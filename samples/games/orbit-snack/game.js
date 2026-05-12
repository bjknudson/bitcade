const canvas = document.querySelector('#game');
const ctx = canvas.getContext('2d');
const keys = new Set();
let player = { x: 100, y: 240, r: 16 };
let snack = { x: 650, y: 240, r: 12 };
let score = 0;
let t = 0;

addEventListener('keydown', (event) => keys.add(event.key));
addEventListener('keyup', (event) => keys.delete(event.key));

function resetSnack() {
  snack.x = 60 + Math.random() * 680;
  snack.y = 60 + Math.random() * 360;
}

function loop() {
  t += 0.035;
  if (keys.has('ArrowLeft')) player.x -= 4;
  if (keys.has('ArrowRight')) player.x += 4;
  if (keys.has('ArrowUp')) player.y -= 4;
  if (keys.has('ArrowDown')) player.y += 4;
  player.x = Math.max(player.r, Math.min(canvas.width - player.r, player.x));
  player.y = Math.max(player.r, Math.min(canvas.height - player.r, player.y));

  const hazard = { x: 400 + Math.cos(t) * 170, y: 240 + Math.sin(t) * 130, r: 24 };
  if (Math.hypot(player.x - snack.x, player.y - snack.y) < player.r + snack.r) {
    score += 1;
    resetSnack();
  }
  if (Math.hypot(player.x - hazard.x, player.y - hazard.y) < player.r + hazard.r) {
    score = 0;
    player = { x: 100, y: 240, r: 16 };
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#f8fbff';
  ctx.font = '24px system-ui';
  ctx.fillText(`Score ${score}`, 24, 38);
  ctx.fillStyle = '#61f0c1';
  ctx.beginPath(); ctx.arc(snack.x, snack.y, snack.r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#ff4d6d';
  ctx.beginPath(); ctx.arc(hazard.x, hazard.y, hazard.r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#ffcf5a';
  ctx.beginPath(); ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2); ctx.fill();
  requestAnimationFrame(loop);
}
loop();
