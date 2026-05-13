let playerX = 200;
let playerY = 200;

function setup() {
  const canvas = createCanvas(400, 400);
  canvas.parent("game-root");
}

function draw() {
  background(18, 22, 40);

  if (keyIsDown(LEFT_ARROW)) playerX -= 3;
  if (keyIsDown(RIGHT_ARROW)) playerX += 3;
  if (keyIsDown(UP_ARROW)) playerY -= 3;
  if (keyIsDown(DOWN_ARROW)) playerY += 3;

  playerX = constrain(playerX, 20, width - 20);
  playerY = constrain(playerY, 20, height - 20);

  fill(97, 240, 193);
  noStroke();
  circle(playerX, playerY, 36);

  fill(248, 251, 255);
  textAlign(CENTER);
  text("Replace sketch.js with your game code", width / 2, height - 24);
}
