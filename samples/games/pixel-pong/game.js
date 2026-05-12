const canvas = document.querySelector('#game');
const ctx = canvas.getContext('2d');
const keys = new Set();
const p1 = { x: 30, y: 190, w: 16, h: 100, score: 0 };
const p2 = { x: 754, y: 190, w: 16, h: 100, score: 0 };
let ball = { x: 400, y: 240, vx: 4, vy: 3, r: 10 };

addEventListener('keydown', (event) => keys.add(event.key));
addEventListener('keyup', (event) => keys.delete(event.key));

function reset(direction) {
  ball = { x: 400, y: 240, vx: 4 * direction, vy: (Math.random() > 0.5 ? 3 : -3), r: 10 };
}
function movePaddle(paddle, up, down) {
  if (keys.has(up)) paddle.y -= 5;
  if (keys.has(down)) paddle.y += 5;
  paddle.y = Math.max(0, Math.min(canvas.height - paddle.h, paddle.y));
}
function hits(paddle) {
  return ball.x + ball.r > paddle.x && ball.x - ball.r < paddle.x + paddle.w && ball.y > paddle.y && ball.y < paddle.y + paddle.h;
}
function loop() {
  movePaddle(p1, 'w', 's');
  movePaddle(p2, 'ArrowUp', 'ArrowDown');
  ball.x += ball.vx;
  ball.y += ball.vy;
  if (ball.y < ball.r || ball.y > canvas.height - ball.r) ball.vy *= -1;
  if (hits(p1) && ball.vx < 0) ball.vx *= -1.08;
  if (hits(p2) && ball.vx > 0) ball.vx *= -1.08;
  if (ball.x < 0) { p2.score += 1; reset(1); }
  if (ball.x > canvas.width) { p1.score += 1; reset(-1); }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#2c345f';
  for (let y = 0; y < canvas.height; y += 32) ctx.fillRect(396, y, 8, 18);
  ctx.fillStyle = '#61f0c1'; ctx.fillRect(p1.x, p1.y, p1.w, p1.h);
  ctx.fillStyle = '#ffcf5a'; ctx.fillRect(p2.x, p2.y, p2.w, p2.h);
  ctx.fillStyle = '#f8fbff';
  ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2); ctx.fill();
  ctx.font = '32px system-ui'; ctx.fillText(`${p1.score}`, 330, 48); ctx.fillText(`${p2.score}`, 450, 48);
  requestAnimationFrame(loop);
}
loop();
