import { useEffect, useRef, useState, useCallback } from "react";

// ── Constants ──────────────────────────────────────────────────────────────────
const WIDTH = 800;
const HEIGHT = 500;
const GRAVITY = 0.25;
const FRICTION = 0.99;
const BOUNCE = 0.75;
const GROUND_H = 40;
const GROUND_Y = HEIGHT - GROUND_H;
const REPLAY_FRAMES = 180;
const REPLAY_FRAME_MS = 12;
const GOAL_TOP = 150;
const GOAL_BOT = 360;
const GOAL_DEPTH = 50;
const BOOST_MAX = 100;
const BOOST_DRAIN = 1.2;
const BOOST_REGEN = 0.15;
const BALL_RADIUS = 16;
const MATCH_SECONDS = 90;
const KICKOFF_TICKS = 180;

type AiLevel = "EASY" | "MEDIUM" | "HARD" | "EXPERT";
type Phase = "kickoff" | "playing" | "replay" | "gameover";
type CarType = "OCTANE" | "FENNEC" | "MERC";

const CAR_TYPES: CarType[] = ["OCTANE", "FENNEC", "MERC"];
const CAR_TYPE_CONFIGS: Record<CarType, { width:number; height:number; powerStat:number; boostColor:string; speed:number }> = {
  OCTANE: { width: 36, height: 16, powerStat: 1.4, boostColor: "#ff6400", speed: 0.60 },
  FENNEC: { width: 34, height: 20, powerStat: 1.5, boostColor: "#00c8ff", speed: 0.55 },
  MERC:   { width: 40, height: 26, powerStat: 1.8, boostColor: "#b4b4b4", speed: 0.45 },
};

// Pre-compute egg fan positions (wider spacing to match oval shapes)
interface FanDot { x: number; y: number; colorKey: number }
const FANS: FanDot[] = [];
for (let x = 40; x < WIDTH; x += 60)
  for (let y = 60; y < 140; y += 35)
    FANS.push({ x, y, colorKey: x % 90 });
// Not used for egg fans but kept for potential future use
function fanColor(_k: number) { return "#ffffff"; }

// ── Types ─────────────────────────────────────────────────────────────────────
interface ConfettiPiece {
  x: number; y: number; vx: number; vy: number;
  color: string; size: number; rot: number; rotV: number;
}
interface FanSign {
  x: number; y: number; msg: string; timer: number; maxTimer: number; offsetY: number;
}
interface BallData { x: number; y: number; vx: number; vy: number; radius: number; angle: number; }
interface CarData {
  x: number; y: number; vx: number; vy: number;
  onGround: boolean; canDoubleJump: boolean; jumpCooldown: number;
  boostFuel: number; isBoosting: boolean;
  // Dynamic per-goal randomized car type + stats
  carType: CarType; width: number; height: number; powerStat: number; boostColor: string; speed: number;
}
interface HistoryFrame {
  ball: { x: number; y: number; angle: number };
  cars: Array<{
    x: number; y: number; isBoosting: boolean; boostFuel: number;
    carType: CarType; width: number; height: number; powerStat: number;
    boostColor: string; speed: number;
  }>;
}
interface CarDef {
  startX: number; color: string;
  jumpPower: number; doubleJumpPower: number; facingRight: boolean;
  keys: { left: string; right: string; jump: string; boost: string };
}

const CAR_DEFS: CarDef[] = [
  { startX: 80,  color: "#3296ff", jumpPower: -7.5, doubleJumpPower: -6.5, facingRight: true,
    keys: { left: "ArrowLeft", right: "ArrowRight", jump: "ArrowUp", boost: " " } },
  { startX: 680, color: "#ff6432", jumpPower: -7.5, doubleJumpPower: -6.5, facingRight: false,
    keys: { left: "a", right: "d", jump: "w", boost: "Shift" } },
];

// ── Factory helpers ────────────────────────────────────────────────────────────
function makeBall(): BallData { return { x: WIDTH/2, y: HEIGHT/2, vx: 0, vy: 0, radius: BALL_RADIUS, angle: 0 }; }

function pickCarType(): CarType { return CAR_TYPES[Math.floor(Math.random()*CAR_TYPES.length)]; }

function makeCar(def: CarDef): CarData {
  const carType = pickCarType();
  const cfg = CAR_TYPE_CONFIGS[carType];
  return { x: def.startX, y: GROUND_Y - cfg.height - 6,
    vx: 0, vy: 0, onGround: true, canDoubleJump: true,
    jumpCooldown: 0, boostFuel: BOOST_MAX, isBoosting: false,
    carType, width: cfg.width, height: cfg.height,
    powerStat: cfg.powerStat, boostColor: cfg.boostColor, speed: cfg.speed };
}

// team: 0 = blue scored, 1 = orange/AI scored; style: "NORMAL" or "SMOKE" (MERC)
function makeConfetti(cx: number, cy: number, team: number, style: "NORMAL"|"SMOKE" = "NORMAL"): ConfettiPiece[] {
  const mult = style === "SMOKE" ? 0.6 : 1.2;
  const COLORS = style === "SMOKE"
    ? ["#888888", "#aaaaaa", "#666666", "#cccccc", "#999999"]
    : team === 0
      ? ["#3296ff", "#3296ff", "#88ddff", "#ffffff", "#ffcc00"]
      : ["#ff8000", "#ff8000", "#ffd040", "#ffffff", "#ff4400"];
  return Array.from({ length: 350 }, () => ({
    x: cx + (Math.random() - 0.5) * 80, y: cy + (Math.random() - 0.5) * 60,
    vx: (Math.random() - 0.5) * 30 * mult,
    vy: -(Math.random() * 17 + 5) * mult,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    size: 4 + Math.floor(Math.random() * 7),
    rot: Math.random() * Math.PI * 2, rotV: (Math.random() - 0.5) * 0.35,
  }));
}

function formatTime(secs: number): string {
  const s = Math.max(0, Math.ceil(secs));
  return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;
}

// ── Physics helpers ────────────────────────────────────────────────────────────
function applyCarPhysics(car: CarData, def: CarDef) {
  if (car.jumpCooldown > 0) car.jumpCooldown--;
  car.vy += GRAVITY; car.vx *= 0.91;
  car.x += car.vx; car.y += car.vy;
  car.x = Math.max(0, Math.min(WIDTH - car.width, car.x));
  if (car.y >= GROUND_Y - car.height - 6) {
    car.y = GROUND_Y - car.height - 6;
    car.vy = 0; car.onGround = true; car.canDoubleJump = true;
  } else car.onGround = false;
}

function carMove(
  car: CarData, def: CarDef,
  dir: "left"|"right"|null, jumpReq: boolean, boostReq: boolean
) {
  // Boost
  const boosting = boostReq && car.boostFuel > 0;
  car.isBoosting = boosting;
  car.boostFuel = boosting
    ? Math.max(0, car.boostFuel - BOOST_DRAIN)
    : Math.min(BOOST_MAX, car.boostFuel + BOOST_REGEN);
  const spd = car.speed * (boosting ? 2.5 : 1.0);

  if (dir === "left") car.vx -= spd;
  if (dir === "right") car.vx += spd;

  // Jump / double-jump
  if (jumpReq && car.jumpCooldown === 0) {
    if (car.onGround) {
      car.vy = def.jumpPower; car.onGround = false; car.jumpCooldown = 20;
    } else if (car.canDoubleJump) {
      car.vy = def.doubleJumpPower; car.canDoubleJump = false; car.jumpCooldown = 25;
    }
  }
}

function runAI(car: CarData, def: CarDef, ball: BallData, level: AiLevel) {
  const targetX = ball.x - car.width / 2;
  const dist = targetX - car.x;

  const cfg = {
    EASY:   { range: 300, canJump: false, canBoost: false, canDoubleJump: false },
    MEDIUM: { range: 500, canJump: true,  canBoost: false, canDoubleJump: false },
    HARD:   { range: 1000,canJump: true,  canBoost: true,  canDoubleJump: false },
    EXPERT: { range: 1000,canJump: true,  canBoost: true,  canDoubleJump: true  },
  }[level];

  let dir: "left"|"right"|null = null;
  let jumpReq = false;
  let boostReq = false;

  if (Math.abs(dist) < cfg.range) {
    if (dist > 10) dir = "right";
    else if (dist < -10) dir = "left";

    if (cfg.canJump && ball.y < car.y - 50 && Math.abs(dist) < 50) jumpReq = true;
    if (cfg.canDoubleJump && !car.onGround && ball.y < car.y) jumpReq = true;
    if (cfg.canBoost && Math.abs(dist) > 150) boostReq = true;
  }

  carMove(car, def, dir, jumpReq, boostReq);
}

function updateBall(ball: BallData) {
  ball.vy += GRAVITY; ball.x += ball.vx; ball.y += ball.vy;
  ball.vx *= FRICTION; ball.angle += ball.vx * 0.04;

  const inGoalZone = ball.y > GOAL_TOP && ball.y < GOAL_BOT;
  if (inGoalZone) {
    // Ball travels into the net — only stop at the back wall
    if (ball.x < -ball.radius) { ball.vx = 0; ball.x = -ball.radius; }
    if (ball.x > WIDTH + ball.radius) { ball.vx = 0; ball.x = WIDTH + ball.radius; }
  } else {
    // Normal side-wall bounce outside goal zone
    if (ball.x - ball.radius < GOAL_DEPTH) { ball.vx *= -BOUNCE; ball.x = GOAL_DEPTH + ball.radius; }
    if (ball.x + ball.radius > WIDTH - GOAL_DEPTH) { ball.vx *= -BOUNCE; ball.x = WIDTH - GOAL_DEPTH - ball.radius; }
  }

  if (ball.y - ball.radius < 156) { ball.vy *= -BOUNCE; ball.y = 156 + ball.radius; }
  if (ball.y + ball.radius > GROUND_Y - 6) { ball.vy *= -BOUNCE; ball.y = GROUND_Y - 6 - ball.radius; }
}

function carBallCollision(car: CarData, def: CarDef, ball: BallData): boolean {
  const ix = 5, iy = 5;
  const cx1 = car.x - ix, cx2 = car.x + car.width + ix;
  const cy1 = car.y - iy, cy2 = car.y + car.height + iy;
  const clX = Math.max(cx1, Math.min(ball.x, cx2));
  const clY = Math.max(cy1, Math.min(ball.y, cy2));
  const dx = ball.x - clX, dy = ball.y - clY;
  const dist = Math.sqrt(dx*dx + dy*dy);
  if (dist < ball.radius + 2) {
    const mult = car.powerStat * (car.isBoosting ? 1.4 : 1.0);
    ball.vx = car.vx * mult + (ball.x > car.x ? 4 : -4);
    ball.vy = -6;
    if (dist > 0.01) { ball.x += (dx/dist)*(ball.radius+3-dist); ball.y += (dy/dist)*(ball.radius+3-dist); }
    else ball.y -= 8;
    return true;
  }
  return false;
}

function checkGoal(ball: BallData): number {
  // Ball must be deep inside the net (past the post face) and at goal height
  if (ball.y > GOAL_TOP && ball.y < GOAL_BOT) {
    if (ball.x > WIDTH - 5) return 0;  // P1/blue scores into right goal
    if (ball.x < 5)         return 1;  // P2/orange scores into left goal
  }
  return -1;
}

// ── Drawing ────────────────────────────────────────────────────────────────────
function drawStadium(ctx: CanvasRenderingContext2D, timeTick: number) {
  ctx.fillStyle = "#12122a"; ctx.fillRect(0, 0, WIDTH, 148);
  // Egg fans: team-colored oval body + two black dot eyes, bobbing with sine wave
  // Blue on left half, Orange on right half (matching team sides)
  for (const f of FANS) {
    const jump = Math.sin(timeTick * 0.15 + f.x) * 6;
    const fy = f.y + jump;
    ctx.fillStyle = f.x < WIDTH / 2 ? "#3296ff" : "#ff6432";
    ctx.beginPath(); ctx.ellipse(f.x + 8, fy + 11, 8, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#000000";
    ctx.beginPath(); ctx.arc(f.x + 5, fy + 8, 1.5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(f.x + 11, fy + 8, 1.5, 0, Math.PI * 2); ctx.fill();
  }
  ctx.fillStyle = "#252525"; ctx.fillRect(0, 148, WIDTH, 8);
  for (let i = 0; i * 80 < WIDTH; i++) {
    ctx.fillStyle = i % 2 === 0 ? "#22742a" : "#32cd3a";
    ctx.fillRect(i * 80, GROUND_Y, 80, GROUND_H);
  }
  ctx.fillStyle = "rgba(0,0,0,0.25)"; ctx.fillRect(0, GROUND_Y, WIDTH, 2);
  ctx.strokeStyle = "rgba(255,255,255,0.1)"; ctx.lineWidth = 2;
  ctx.setLineDash([10,8]);
  ctx.beginPath(); ctx.moveTo(WIDTH/2,156); ctx.lineTo(WIDTH/2,GROUND_Y); ctx.stroke();
  ctx.setLineDash([]);
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(WIDTH/2, (156+GROUND_Y)/2, 70, 0, Math.PI*2); ctx.stroke();
}

function drawGoalNets(ctx: CanvasRenderingContext2D) {
  const netH = GOAL_BOT - GOAL_TOP;
  const a = "rgba(255,255,255,0.5)";
  [[WIDTH-GOAL_DEPTH, 1],[0, -1]].forEach(([gx,_]) => {
    ctx.strokeStyle = a; ctx.lineWidth = 1;
    ctx.strokeRect(gx, GOAL_TOP, GOAL_DEPTH, netH);
    for (let y = GOAL_TOP; y <= GOAL_BOT; y += 25) {
      ctx.beginPath(); ctx.moveTo(gx, y); ctx.lineTo(gx+GOAL_DEPTH, y); ctx.stroke();
    }
    for (let x = gx; x <= gx+GOAL_DEPTH; x += 12) {
      ctx.beginPath(); ctx.moveTo(x, GOAL_TOP); ctx.lineTo(x, GOAL_BOT); ctx.stroke();
    }
    ctx.strokeStyle = "#cccccc"; ctx.lineWidth = 3;
    ctx.strokeRect(gx-1, GOAL_TOP, GOAL_DEPTH+1, netH);
  });
}

function drawBall(ctx: CanvasRenderingContext2D, ball: BallData) {
  ctx.beginPath(); ctx.ellipse(ball.x, GROUND_Y-3, ball.radius*0.65, 4, 0, 0, Math.PI*2);
  ctx.fillStyle = "rgba(0,0,0,0.2)"; ctx.fill();
  const g = ctx.createRadialGradient(ball.x-6, ball.y-6, 2, ball.x, ball.y, ball.radius);
  g.addColorStop(0,"#ffffff"); g.addColorStop(0.55,"#eeeeee"); g.addColorStop(1,"#bbbbbb");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI*2); ctx.fill();
  ctx.strokeStyle = "rgba(50,50,50,0.5)"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI*2); ctx.stroke();
  // Soccer ball: 5 pentagon spots rotating with ball.angle
  ctx.fillStyle = "#1a1a1a";
  for (let i = 0; i < 5; i++) {
    const ang = ball.angle + (i * Math.PI * 2) / 5;
    const px = ball.x + Math.cos(ang) * (ball.radius * 0.5);
    const py = ball.y + Math.sin(ang) * (ball.radius * 0.5);
    ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill();
  }
}

// Mirror a set of polygon points around the car's horizontal center
function mirrorPts(pts: [number,number][], x: number, W: number): [number,number][] {
  return pts.map(([px,py]) => [x + W - (px - x), py]);
}

function drawCar(ctx: CanvasRenderingContext2D, car: CarData, def: CarDef, label: string|null) {
  const { x, y } = car;
  const W = car.width; const H = car.height;
  const fr = def.facingRight;

  // Boost flame — behind the car, using per-type color
  if (car.isBoosting) {
    const fx = fr ? x - 8 : x + W + 2;
    const r = 4 + Math.random()*7;
    ctx.beginPath(); ctx.arc(fx, y+H*0.55, r, 0, Math.PI*2);
    ctx.fillStyle = car.boostColor + "cc"; ctx.fill();
    ctx.beginPath(); ctx.arc(fx, y+H*0.55, r*0.45, 0, Math.PI*2);
    ctx.fillStyle = "#ffffff99"; ctx.fill();
  }

  // Double-jump glow
  if (!car.onGround && car.canDoubleJump) {
    ctx.strokeStyle = "rgba(255,220,60,0.4)"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.roundRect(x-3, y-3, W+6, H+6, 5); ctx.stroke();
  }

  // ── Body polygon (per car type, then mirror if facing left) ──────────────────
  let bodyPts: [number,number][];
  let winPts:  [number,number][];

  if (car.carType === "FENNEC") {
    // Boxy hatchback — raised bottom, full rectangle
    bodyPts = [[x,y+3],[x+W,y+3],[x+W,y+H],[x,y+H]];
    const rawWin: [number,number][] = [[x+4,y+5],[x+W-6,y+5],[x+W-6,y+12],[x+4,y+12]];
    winPts = fr ? rawWin : mirrorPts(rawWin, x, W);
    // Rear spoiler nub
    if (fr) { ctx.fillStyle="#1e1e1e"; ctx.fillRect(x-2,y+1,4,8); }
    else     { ctx.fillStyle="#1e1e1e"; ctx.fillRect(x+W-2,y+1,4,8); }

  } else if (car.carType === "MERC") {
    // Heavy truck — angled front cab, flat roof at back
    const rawBody: [number,number][] = [
      [x, y], [x+W-8, y], [x+W, y+10], [x+W, y+H], [x, y+H]
    ];
    bodyPts = fr ? rawBody : mirrorPts(rawBody, x, W);
    const rawWin: [number,number][] = [
      [x+4, y+3], [x+W-12, y+3], [x+W-6, y+12], [x+4, y+12]
    ];
    winPts = fr ? rawWin : mirrorPts(rawWin, x, W);

  } else {
    // OCTANE — sharp wedge, flat bottom
    const rawBody: [number,number][] = [
      [x, y+H], [x+W, y+H], [x+W-6, y+4], [x+10, y]
    ];
    bodyPts = fr ? rawBody : mirrorPts(rawBody, x, W);
    const rawWin: [number,number][] = [
      [x+12, y+2], [x+W-8, y+6], [x+W-12, y+H-4], [x+10, y+H-4]
    ];
    winPts = fr ? rawWin : mirrorPts(rawWin, x, W);
    // Spoiler nub at rear
    if (fr) { ctx.fillStyle="#2a2a2a"; ctx.fillRect(x,y-4,6,12); }
    else     { ctx.fillStyle="#2a2a2a"; ctx.fillRect(x+W-6,y-4,6,12); }
  }

  // Draw body with dark outline
  ctx.beginPath();
  bodyPts.forEach(([px,py],i) => i===0 ? ctx.moveTo(px,py) : ctx.lineTo(px,py));
  ctx.closePath(); ctx.fillStyle = def.color; ctx.fill();
  ctx.strokeStyle = "#1e1e1e"; ctx.lineWidth = 2;
  ctx.beginPath();
  bodyPts.forEach(([px,py],i) => i===0 ? ctx.moveTo(px,py) : ctx.lineTo(px,py));
  ctx.closePath(); ctx.stroke();

  // Draw window
  ctx.beginPath();
  winPts.forEach(([px,py],i) => i===0 ? ctx.moveTo(px,py) : ctx.lineTo(px,py));
  ctx.closePath(); ctx.fillStyle = "rgba(200,230,255,0.65)"; ctx.fill();

  // Wheels — centered at bottom of car (y+H)
  const wbaseY = y + H;
  [[x+8, wbaseY],[x+W-8, wbaseY]].forEach(([wx,wy]) => {
    ctx.beginPath(); ctx.arc(wx,wy,6,0,Math.PI*2); ctx.fillStyle="#141414"; ctx.fill();
    ctx.strokeStyle="#444"; ctx.lineWidth=1.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(wx,wy,2.5,0,Math.PI*2); ctx.fillStyle="#666"; ctx.fill();
  });

  if (label) {
    ctx.font="bold 10px monospace"; ctx.textAlign="center";
    ctx.fillStyle="rgba(255,255,255,0.7)"; ctx.fillText(label, x+W/2, y-14);
  }
}

function drawHUD(
  ctx: CanvasRenderingContext2D, cars: CarData[], scores: number[],
  gameMode: string, aiLevel: AiLevel, matchSecsLeft: number, phase: Phase,
  kickTick: number, replayFrame: number, replayTotal: number, scorerText: string
) {
  ctx.font = "bold 34px Impact, monospace"; ctx.textAlign = "center";
  if (matchSecsLeft <= 30) { ctx.shadowColor="#ff3232"; ctx.shadowBlur=12; ctx.fillStyle="#ff5555"; }
  else ctx.fillStyle = "#ffffff";
  ctx.fillText(formatTime(matchSecsLeft), WIDTH/2, 42); ctx.shadowBlur = 0;

  ctx.font = "bold 20px monospace";
  ctx.fillStyle="#3296ff"; ctx.fillText(`${scores[0]}`, WIDTH/2-60, 65);
  ctx.fillStyle="rgba(255,255,255,0.25)"; ctx.fillText("-", WIDTH/2, 65);
  ctx.fillStyle="#ff6432"; ctx.fillText(`${scores[1]}`, WIDTH/2+60, 65);

  // AI level badge (1p only)
  if (gameMode === "1p") {
    const lvlColors: Record<AiLevel,string> = { EASY:"#44cc44", MEDIUM:"#ffd040", HARD:"#ff7700", EXPERT:"#ff3232" };
    ctx.font = "bold 10px monospace"; ctx.textAlign = "right";
    ctx.fillStyle = lvlColors[aiLevel];
    ctx.fillText(`AI: ${aiLevel}`, WIDTH-16, 16);
  }

  // Boost bars
  for (let i = 0; i < cars.length; i++) {
    const car = cars[i];
    const bx = i === 0 ? 16 : WIDTH-116; const by = 14;
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.beginPath(); ctx.roundRect(bx, by, 100, 14, 5); ctx.fill();
    const pct = car.boostFuel / BOOST_MAX;
    if (pct > 0) {
      const bg = ctx.createLinearGradient(bx,by,bx+100,by);
      bg.addColorStop(0,"#cc7700"); bg.addColorStop(1,"#ffcc00");
      ctx.fillStyle = bg;
      ctx.beginPath(); ctx.roundRect(bx,by,100*pct,14,5); ctx.fill();
      if (car.isBoosting) {
        ctx.shadowColor="#ffcc00"; ctx.shadowBlur=10;
        ctx.beginPath(); ctx.roundRect(bx,by,100*pct,14,5); ctx.fill(); ctx.shadowBlur=0;
      }
    }
    ctx.font="bold 9px monospace";
    ctx.textAlign = i===0?"left":"right";
    ctx.fillStyle="rgba(255,200,60,0.8)";
    ctx.fillText("BOOST", i===0?bx:bx+100, by-2);
  }

  // Controls hint
  ctx.font="10px monospace"; ctx.fillStyle="rgba(255,255,255,0.22)";
  if (gameMode==="2p") {
    ctx.textAlign="left"; ctx.fillText("P1: ← → ↑  [Space] boost", 16, HEIGHT-10);
    ctx.textAlign="right"; ctx.fillText("P2: A D W  [Shift] boost", WIDTH-16, HEIGHT-10);
  } else {
    ctx.textAlign="left"; ctx.fillText("← → ↑  [Space] boost   ↑↑ double-jump", 16, HEIGHT-10);
  }

  // Kickoff overlay
  if (phase==="kickoff") {
    ctx.fillStyle="rgba(0,0,0,0.45)"; ctx.fillRect(0,0,WIDTH,HEIGHT);
    const txt = kickTick>120?"READY":kickTick>60?"SET":"GO!";
    const col = kickTick>120?"#ffffff":kickTick>60?"#ffd040":"#44ff88";
    ctx.font="bold 72px Impact, monospace"; ctx.textAlign="center";
    ctx.fillStyle=col; ctx.shadowColor=col; ctx.shadowBlur=24;
    ctx.fillText(txt, WIDTH/2, HEIGHT/2+22); ctx.shadowBlur=0;
  }

  // Replay overlay
  if (phase==="replay") {
    ctx.fillStyle="rgba(0,0,0,0.42)"; ctx.fillRect(0,0,WIDTH,HEIGHT);
    ctx.font="bold 42px Impact, monospace"; ctx.textAlign="center";
    ctx.fillStyle="#ffd040"; ctx.shadowColor="#ffd040"; ctx.shadowBlur=20;
    ctx.fillText("REPLAY", WIDTH/2, HEIGHT/2-12); ctx.shadowBlur=0;
    const pbw=200, pbx=(WIDTH-pbw)/2;
    ctx.fillStyle="rgba(255,255,255,0.1)";
    ctx.beginPath(); ctx.roundRect(pbx, HEIGHT/2+12, pbw, 6, 3); ctx.fill();
    ctx.fillStyle="#ffd040";
    ctx.beginPath(); ctx.roundRect(pbx, HEIGHT/2+12, pbw*(replayFrame/Math.max(1,replayTotal)), 6, 3); ctx.fill();
    // Scorer banner at bottom
    if (scorerText) {
      ctx.fillStyle="rgba(180,0,0,0.82)"; ctx.fillRect(0, HEIGHT-52, WIDTH, 44);
      ctx.font="bold 18px Impact, monospace"; ctx.textAlign="center";
      ctx.fillStyle="#ffffff"; ctx.fillText(scorerText, WIDTH/2, HEIGHT-24);
    }
  }

  // Game over overlay
  if (phase==="gameover") {
    ctx.fillStyle="rgba(0,0,0,0.6)"; ctx.fillRect(0,0,WIDTH,HEIGHT);
    ctx.font="bold 70px Impact, monospace"; ctx.textAlign="center";
    ctx.fillStyle="#ff3232"; ctx.shadowColor="#ff3232"; ctx.shadowBlur=28;
    ctx.fillText("GAME OVER", WIDTH/2, HEIGHT/2-10); ctx.shadowBlur=0;
    ctx.font="bold 24px monospace"; ctx.fillStyle="#ffffff";
    const winner = scores[0]>scores[1]?"BLUE WINS!":scores[1]>scores[0]?"ORANGE WINS!":"DRAW!";
    ctx.fillText(winner, WIDTH/2, HEIGHT/2+36);
    ctx.font="13px monospace"; ctx.fillStyle="rgba(255,255,255,0.4)";
    ctx.fillText("press MENU to restart", WIDTH/2, HEIGHT/2+66);
  }
}

function drawFanSigns(ctx: CanvasRenderingContext2D, signs: FanSign[]) {
  ctx.font = "bold 11px Impact, monospace";
  for (const s of signs) {
    if (s.timer <= 0) continue;
    const alpha = Math.min(1, s.timer / 30);
    const sy = s.y + s.offsetY;
    const w = ctx.measureText(s.msg).width + 14;
    ctx.save(); ctx.globalAlpha = alpha;
    // Gold or white alternating
    const isGold = s.msg === "GOAL!!" || s.msg === "WHAT A SAVE!";
    ctx.fillStyle = "#141420";
    ctx.beginPath(); ctx.roundRect(s.x - w/2, sy - 10, w, 18, 4); ctx.fill();
    ctx.strokeStyle = isGold ? "#ffd040" : "#ffffff55"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect(s.x - w/2, sy - 10, w, 18, 4); ctx.stroke();
    ctx.fillStyle = isGold ? "#ffd040" : "#ffffff";
    ctx.textAlign = "center"; ctx.fillText(s.msg, s.x, sy + 4);
    ctx.restore();
  }
}

function drawScene(
  ctx: CanvasRenderingContext2D, ball: BallData, cars: CarData[],
  confetti: ConfettiPiece[], signs: FanSign[], scores: number[], gameMode: string, aiLevel: AiLevel,
  matchSecsLeft: number, phase: Phase, kickTick: number,
  replayFrame: number, replayTotal: number, timeTick: number, shake: number, scorerText: string
) {
  ctx.fillStyle="#0d1117"; ctx.fillRect(0,0,WIDTH,HEIGHT);
  // Screen shake — random offset applied to the whole scene
  if (shake > 0) {
    const rx = (Math.random()-0.5)*shake*2;
    const ry = (Math.random()-0.5)*shake*2;
    ctx.save(); ctx.translate(rx, ry);
  }
  drawStadium(ctx, timeTick);
  drawGoalNets(ctx);
  drawFanSigns(ctx, signs);
  for (const c of confetti) {
    ctx.save(); ctx.translate(c.x,c.y); ctx.rotate(c.rot);
    ctx.fillStyle=c.color; ctx.fillRect(-c.size/2,-c.size/2,c.size,c.size); ctx.restore();
  }
  for (let i=0;i<cars.length;i++)
    drawCar(ctx, cars[i], CAR_DEFS[i], gameMode==="1p"&&i===1?"AI":null);
  drawBall(ctx, ball);
  if (shake > 0) ctx.restore();
  drawHUD(ctx, cars, scores, gameMode, aiLevel, matchSecsLeft, phase, kickTick, replayFrame, replayTotal, scorerText);
}

// ── Component ─────────────────────────────────────────────────────────────────
type MenuScreen = "main" | "difficulty";

export default function Game() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const keysRef = useRef<Set<string>>(new Set());
  const stateRef = useRef({
    ball: makeBall(), cars: CAR_DEFS.map(makeCar),
    confetti: [] as ConfettiPiece[], signs: [] as FanSign[], scores: [0,0], shake: 0,
    mode: "2p" as "1p"|"2p", aiLevel: "HARD" as AiLevel,
    phase: "kickoff" as Phase, kickTick: KICKOFF_TICKS,
    matchSecsLeft: MATCH_SECONDS, history: [] as HistoryFrame[], timeTick: 0,
    lastScorerText: "",
  });
  const [scores, setScores] = useState([0,0]);
  const [started, setStarted] = useState(false);
  const [menuScreen, setMenuScreen] = useState<MenuScreen>("main");
  const rafRef = useRef<number>(0);
  const replayTimerRef = useRef<ReturnType<typeof setTimeout>|null>(null);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    keysRef.current.add(e.key);
    if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"," "].includes(e.key)) e.preventDefault();
  },[]);
  const handleKeyUp = useCallback((e: KeyboardEvent) => keysRef.current.delete(e.key),[]);
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown, { passive:false });
    window.addEventListener("keyup", handleKeyUp);
    return ()=>{ window.removeEventListener("keydown",handleKeyDown); window.removeEventListener("keyup",handleKeyUp); };
  },[handleKeyDown,handleKeyUp]);

  const doKickoff = useCallback(() => {
    const st = stateRef.current;
    st.ball = makeBall(); st.cars = CAR_DEFS.map(makeCar);
    st.confetti = []; st.signs = []; st.history = []; st.shake = 0;
    st.phase = "kickoff"; st.kickTick = KICKOFF_TICKS;
  },[]);

  const startGame = useCallback((mode: "1p"|"2p", level: AiLevel = "HARD") => {
    const st = stateRef.current;
    st.mode = mode; st.aiLevel = level;
    st.scores = [0,0]; st.matchSecsLeft = MATCH_SECONDS; st.timeTick = 0;
    setScores([0,0]); setMenuScreen("main");
    doKickoff(); setStarted(true);
  },[doKickoff]);

  const runReplayStep = useCallback((
    canvas: HTMLCanvasElement, history: HistoryFrame[], idx: number,
    confetti: ConfettiPiece[], scores: number[], matchSecsLeft: number,
    mode: string, aiLevel: AiLevel, timeTick: number
  ) => {
    const ctx = canvas.getContext("2d")!;
    if (idx >= history.length) {
      const st = stateRef.current;
      if (st.matchSecsLeft <= 0) st.phase = "gameover";
      else doKickoff();
      return;
    }
    const frame = history[idx];
    const ball: BallData = { ...frame.ball, vx:0, vy:0, radius:BALL_RADIUS };
    const cars: CarData[] = frame.cars.map(c=>({
      x:c.x, y:c.y, vx:0, vy:0, onGround:true, canDoubleJump:true,
      jumpCooldown:0, boostFuel:c.boostFuel, isBoosting:c.isBoosting,
      carType:c.carType, width:c.width, height:c.height,
      powerStat:c.powerStat, boostColor:c.boostColor, speed:c.speed,
    }));
    drawScene(ctx,ball,cars,confetti,[],scores,mode,aiLevel,matchSecsLeft,"replay",0,idx,history.length,timeTick+idx,0,stateRef.current.lastScorerText);
    replayTimerRef.current = setTimeout(()=>{
      runReplayStep(canvas,history,idx+1,confetti,scores,matchSecsLeft,mode,aiLevel,timeTick);
    }, REPLAY_FRAME_MS);
  },[doKickoff]);

  useEffect(()=>{
    if(!started) return;
    const canvas = canvasRef.current; if(!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let last = performance.now();

    function loop(now: number) {
      const st = stateRef.current;
      const dt = Math.min((now-last)/16.67, 3); last = now;
      st.timeTick += dt;

      // Confetti + signs always update
      for (let i=st.confetti.length-1;i>=0;i--) {
        const c=st.confetti[i]; c.x+=c.vx; c.y+=c.vy; c.vy+=0.1; c.rot+=c.rotV;
        if(c.y>HEIGHT+20) st.confetti.splice(i,1);
      }
      for (let i=st.signs.length-1;i>=0;i--) {
        const sg=st.signs[i]; sg.timer--; sg.offsetY-=0.5;
        if(sg.timer<=0) st.signs.splice(i,1);
      }
      if(st.shake>0) st.shake=Math.max(0,st.shake-1);

      if (st.phase==="kickoff") {
        st.kickTick -= dt; if(st.kickTick<=0) st.phase="playing";

      } else if (st.phase==="playing") {
        const steps = Math.round(dt);
        for(let s=0;s<steps;s++){
          // Player 1
          const k = keysRef.current;
          const p1Def = CAR_DEFS[0];
          const p1Dir = k.has(p1Def.keys.left)?"left":k.has(p1Def.keys.right)?"right":null;
          carMove(st.cars[0], p1Def, p1Dir, k.has(p1Def.keys.jump), k.has(p1Def.keys.boost));
          applyCarPhysics(st.cars[0], p1Def);

          // Player 2 / AI
          if(st.mode==="2p"){
            const p2Def = CAR_DEFS[1];
            const p2Dir = k.has(p2Def.keys.left)?"left":k.has(p2Def.keys.right)?"right":null;
            carMove(st.cars[1], p2Def, p2Dir, k.has(p2Def.keys.jump), k.has(p2Def.keys.boost));
            applyCarPhysics(st.cars[1], p2Def);
          } else {
            runAI(st.cars[1], CAR_DEFS[1], st.ball, st.aiLevel);
            applyCarPhysics(st.cars[1], CAR_DEFS[1]);
          }

          updateBall(st.ball);
          for(let i=0;i<st.cars.length;i++){
            const hit = carBallCollision(st.cars[i],CAR_DEFS[i],st.ball);
            if(hit && st.shake < 5) st.shake = 5;
          }
        }

        st.matchSecsLeft -= dt/60;

        // History
        st.history.push({
          ball:{x:st.ball.x,y:st.ball.y,angle:st.ball.angle},
          cars:st.cars.map(c=>({
            x:c.x, y:c.y, isBoosting:c.isBoosting, boostFuel:c.boostFuel,
            carType:c.carType, width:c.width, height:c.height,
            powerStat:c.powerStat, boostColor:c.boostColor, speed:c.speed,
          })),
        });
        if(st.history.length>REPLAY_FRAMES) st.history.shift();

        // Goal?
        const side = checkGoal(st.ball);
        if(side>=0){
          st.scores[side]+=1; setScores([...st.scores]);
          // Screen shake on goal
          st.shake = 20;
          // Scorer text: "BLUE FENNEC SCORED!"
          const scorerLabel = side===0 ? "BLUE" : (st.mode==="1p"?"AI":"ORANGE");
          const scorerCar = st.cars[side===0?0:1].carType;
          st.lastScorerText = `${scorerLabel} ${scorerCar} SCORED!`;
          // MERC gets grey smoke confetti, others get team-coloured burst
          const confStyle: "NORMAL"|"SMOKE" = scorerCar==="MERC" ? "SMOKE" : "NORMAL";
          const confCx = side===0 ? WIDTH-30 : 30;
          st.confetti.push(...makeConfetti(confCx, (GOAL_TOP+GOAL_BOT)/2, side, confStyle));
          // Fan signs — always 12, floating upward
          const msgs = ["GOAL!!", "WHAT A SAVE!", "OMG!", "LETS GO!", "WOOO!", "SICK!"];
          st.signs = Array.from({length:12}, ()=>({
            x: 100 + Math.random()*(WIDTH-200),
            y: 50 + Math.random()*100,
            msg: msgs[Math.floor(Math.random()*msgs.length)],
            timer: 140, maxTimer: 140, offsetY: 0,
          }));
          st.phase="replay";
          const hC=[...st.history],cC=[...st.confetti],sC=[...st.scores];
          const mS=st.matchSecsLeft,mD=st.mode,aL=st.aiLevel,tT=st.timeTick;
          if(replayTimerRef.current) clearTimeout(replayTimerRef.current);
          replayTimerRef.current=setTimeout(()=>runReplayStep(canvas,hC,0,cC,sC,mS,mD,aL,tT),500);
        }

        // Timer end
        if(st.matchSecsLeft<=0 && st.ball.y+st.ball.radius>=GROUND_Y-8) st.phase="gameover";
      }

      drawScene(ctx,st.ball,st.cars,st.confetti,st.signs,st.scores,st.mode,st.aiLevel,
        st.matchSecsLeft,st.phase,st.kickTick,0,0,st.timeTick,st.shake,st.lastScorerText);
      rafRef.current=requestAnimationFrame(loop);
    }

    rafRef.current=requestAnimationFrame(loop);
    return()=>{ cancelAnimationFrame(rafRef.current); if(replayTimerRef.current) clearTimeout(replayTimerRef.current); };
  },[started,doKickoff,runReplayStep]);

  // ── Menu ────────────────────────────────────────────────────────────────────
  if (!started) {
    const DIFFICULTIES: { level: AiLevel; color: string; desc: string }[] = [
      { level:"EASY",   color:"#44cc44", desc:"Slow reactions, no boost or jump" },
      { level:"MEDIUM", color:"#ffd040", desc:"Can jump, stays nearby" },
      { level:"HARD",   color:"#ff7700", desc:"Jumps and boosts aggressively" },
      { level:"EXPERT", color:"#ff3232", desc:"Double-jumps, full aggression" },
    ];

    return (
      <div style={{
        width:"100vw", height:"100vh",
        background:"linear-gradient(180deg,#12122a 0%,#1a2a14 100%)",
        display:"flex", flexDirection:"column",
        alignItems:"center", justifyContent:"center",
        fontFamily:"monospace", color:"#fff", gap:28,
      }}>
        <div style={{textAlign:"center"}}>
          <div style={{fontSize:13,color:"#555",letterSpacing:5,marginBottom:8}}>2D PIXEL</div>
          <div style={{
            fontSize:46,fontWeight:"bold",letterSpacing:3,
            background:"linear-gradient(135deg,#3296ff 0%,#ff6432 100%)",
            WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",
          }}>ROCKET LEAGUE</div>
          <div style={{fontSize:12,color:"#666",marginTop:8,letterSpacing:2}}>3 MINUTE MATCH</div>
        </div>

        {menuScreen==="main" && (
          <>
            <div style={{display:"flex",gap:20}}>
              {(["1p","2p"] as const).map(m=>{
                const color=m==="1p"?"#3296ff":"#ff6432";
                return (
                  <button key={m} onClick={()=>m==="1p"?setMenuScreen("difficulty"):startGame("2p")} style={{
                    padding:"14px 36px",fontSize:15,fontFamily:"monospace",fontWeight:"bold",
                    border:`2px solid ${color}`,background:"transparent",color,cursor:"pointer",
                    letterSpacing:2,transition:"all 0.15s",
                  }}
                    onMouseEnter={e=>{const b=e.target as HTMLButtonElement;b.style.background=color;b.style.color="#fff";}}
                    onMouseLeave={e=>{const b=e.target as HTMLButtonElement;b.style.background="transparent";b.style.color=color;}}
                  >{m==="1p"?"1 PLAYER":"2 PLAYERS"}</button>
                );
              })}
            </div>
            <div style={{fontSize:11,color:"#444",textAlign:"center",lineHeight:2.2}}>
              <div>P1: Arrow Keys + <span style={{color:"#ffd040"}}>[Space]</span> Boost · <span style={{color:"#88ccff"}}>↑↑ double-jump</span></div>
              <div>P2: WASD + <span style={{color:"#ffd040"}}>[Shift]</span> Boost</div>
            </div>
          </>
        )}

        {menuScreen==="difficulty" && (
          <>
            <div style={{fontSize:14,color:"#888",letterSpacing:3}}>SELECT AI DIFFICULTY</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,width:420}}>
              {DIFFICULTIES.map(({level,color,desc})=>(
                <button key={level} onClick={()=>startGame("1p",level)} style={{
                  padding:"16px 12px",fontFamily:"monospace",fontWeight:"bold",fontSize:14,
                  border:`2px solid ${color}`,background:"rgba(0,0,0,0.3)",color,
                  cursor:"pointer",letterSpacing:2,transition:"all 0.15s",
                  display:"flex",flexDirection:"column",gap:6,alignItems:"center",
                }}
                  onMouseEnter={e=>{(e.currentTarget as HTMLButtonElement).style.background=color+"33";}}
                  onMouseLeave={e=>{(e.currentTarget as HTMLButtonElement).style.background="rgba(0,0,0,0.3)";}}
                >
                  <span>{level}</span>
                  <span style={{fontSize:9,color:"rgba(255,255,255,0.4)",fontWeight:"normal",letterSpacing:0,textTransform:"none"}}>{desc}</span>
                </button>
              ))}
            </div>
            <button onClick={()=>setMenuScreen("main")} style={{
              padding:"7px 20px",fontFamily:"monospace",fontSize:11,
              background:"transparent",border:"1px solid rgba(255,255,255,0.15)",
              color:"rgba(255,255,255,0.35)",cursor:"pointer",letterSpacing:2,
            }}>← BACK</button>
          </>
        )}
      </div>
    );
  }

  return (
    <div style={{
      width:"100vw",height:"100vh",background:"#0d1117",
      display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:14,
    }}>
      <canvas ref={canvasRef} width={WIDTH} height={HEIGHT} style={{
        display:"block",maxWidth:"100%",maxHeight:"82vh",
        border:"2px solid rgba(255,255,255,0.07)",
      }}/>
      <button onClick={()=>{
        cancelAnimationFrame(rafRef.current);
        if(replayTimerRef.current) clearTimeout(replayTimerRef.current);
        setStarted(false);
      }} style={{
        padding:"7px 22px",fontFamily:"monospace",fontSize:12,
        background:"transparent",border:"1px solid rgba(255,255,255,0.15)",
        color:"rgba(255,255,255,0.4)",cursor:"pointer",letterSpacing:2,
      }}>MENU</button>
    </div>
  );
}
