(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var T = window.THREE;
  if (!T) {
    $("loading").innerHTML = "<span>KHÔNG TẢI ĐƯỢC THREE.JS</span><span style='font:11px sans-serif;letter-spacing:0'>Kiểm tra kết nối mạng rồi tải lại trang.</span>";
    return;
  }

  var stage = $("stage"), renderer, scene, camera, clock = new T.Clock();
  var pointer = { down: false, x: 0, y: 0 }, view = { yaw: 0.82, pitch: 0.53, distance: 10.6 }, focus = new T.Vector3(0, 0.68, 0);
  var mat = function (color, roughness, metalness) { return new T.MeshStandardMaterial({ color: color, roughness: roughness == null ? 0.72 : roughness, metalness: metalness || 0 }); };
  var mats = {
    floor: mat(0x252f34), floorEdge: mat(0x39474b), steel: mat(0x53646b, .42, .72), darkSteel: mat(0x27363c, .48, .55),
    belt: mat(0x192328, .94), rubber: mat(0x11191d, .9), silver: mat(0xb8c2c3, .3, .78), arm: mat(0xdaa24b, .36, .45),
    armDark: mat(0x33464b, .4, .64), cyan: mat(0x63dece, .32, .26), orange: mat(0xf28b4a, .42, .12), black: mat(0x172126, .5, .2),
    basket: mat(0x416d71, .52, .42), label: mat(0xd8e2de, .8), concrete: mat(0x303c40, .85), white: mat(0xe4e7de, .68)
  };

  try {
    renderer = new T.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.35));
    renderer.setSize(stage.clientWidth, stage.clientHeight, false);
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.toneMapping = T.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    stage.appendChild(renderer.domElement);
  } catch (e) {
    $("loading").innerHTML = "<span>KHÔNG KHỞI TẠO ĐƯỢC WEBGL</span><span style='font:11px sans-serif;letter-spacing:0'>Trình duyệt cần bật tăng tốc đồ họa.</span>";
    return;
  }

  scene = new T.Scene();
  scene.background = new T.Color(0x182329);
  scene.fog = new T.Fog(0x182329, 16, 34);
  camera = new T.PerspectiveCamera(38, stage.clientWidth / Math.max(stage.clientHeight, 1), .1, 80);
  scene.add(new T.HemisphereLight(0xcce9eb, 0x252d2e, 2.05));
  var keyLight = new T.DirectionalLight(0xffe5c4, 2.65); keyLight.position.set(-3, 10, 6); scene.add(keyLight);
  var fillLight = new T.DirectionalLight(0x70a6b4, 1.1); fillLight.position.set(5, 5, -7); scene.add(fillLight);
  var warmLight = new T.PointLight(0xffaa69, 17, 8, 2); warmLight.position.set(1, 4, 1); scene.add(warmLight);
  var world = new T.Group(); scene.add(world);

  function box(parent, size, position, material, rotation) {
    var mesh = new T.Mesh(new T.BoxGeometry(size[0], size[1], size[2]), material);
    mesh.position.set(position[0], position[1], position[2]);
    if (rotation) mesh.rotation.set(rotation[0] || 0, rotation[1] || 0, rotation[2] || 0);
    parent.add(mesh); return mesh;
  }
  function cylinder(parent, radiusTop, radiusBottom, height, position, material, segments) {
    var mesh = new T.Mesh(new T.CylinderGeometry(radiusTop, radiusBottom, height, segments || 18), material);
    mesh.position.set(position[0], position[1], position[2]); parent.add(mesh); return mesh;
  }
  function line(parent, points, color, opacity) {
    var geometry = new T.BufferGeometry().setFromPoints(points.map(function (p) { return new T.Vector3(p[0], p[1], p[2]); }));
    var mesh = new T.Line(geometry, new T.LineBasicMaterial({ color: color, transparent: opacity < 1, opacity: opacity == null ? 1 : opacity }));
    parent.add(mesh); return mesh;
  }
  function label(text, color) {
    var canvas = document.createElement("canvas"); canvas.width = 512; canvas.height = 128;
    var ctx = canvas.getContext("2d"); ctx.fillStyle = "rgba(15,24,29,.84)"; ctx.beginPath(); ctx.roundRect(8, 8, 496, 112, 15); ctx.fill();
    ctx.fillStyle = color || "#a6c0c4"; ctx.font = "600 35px 'JetBrains Mono', monospace"; ctx.letterSpacing = "4px"; ctx.fillText(text, 28, 78);
    var texture = new T.CanvasTexture(canvas); texture.encoding = T.sRGBEncoding;
    var sprite = new T.Sprite(new T.SpriteMaterial({ map: texture, transparent: true, depthWrite: false })); sprite.scale.set(1.52, .38, 1); return sprite;
  }

  // Factory floor and restrained layout markings.
  box(world, [15, .16, 11], [0, -.11, 0], mats.floor);
  box(world, [15, .15, .12], [0, -.2, -5.42], mats.floorEdge);
  box(world, [15, .15, .12], [0, -.2, 5.42], mats.floorEdge);
  var grid = new T.GridHelper(14, 28, 0x46555a, 0x344147); grid.position.y = -.025; grid.material.transparent = true; grid.material.opacity = .27; world.add(grid);
  // Cell boundary and a few compact service panels anchor the space without expensive scenery.
  [[-4.6, -2.4], [4.55, -2.4], [-4.6, 3.9], [4.55, 3.9]].forEach(function (p) {
    box(world, [.12, 2.2, .12], [p[0], 1.05, p[1]], mats.darkSteel);
  });
  box(world, [9.25, .08, .12], [0, 2.13, -2.4], mats.steel);
  box(world, [9.25, .08, .12], [0, 2.13, 3.9], mats.steel);
  box(world, [1.15, 1.65, .18], [-4.28, .84, -2.28], mats.black);
  box(world, [.82, .07, .05], [-4.28, 1.48, -2.16], mats.cyan);
  box(world, [.38, .32, .04], [-4.28, .97, -2.16], mats.darkSteel);
  var monitor = box(world, [.28, .16, .025], [-4.28, 1.12, -2.13], mats.cyan);
  monitor.material = new T.MeshStandardMaterial({ color: 0x57d4c5, emissive: 0x17645d, roughness: .35 });
  // Safety markings around the robot cell.
  for (var stripe = -4; stripe < 4.3; stripe += .46) {
    box(world, [.25, .012, .105], [stripe, -.018, 2.77], mats.orange);
    box(world, [.25, .012, .105], [stripe, -.018, -2.72], mats.orange);
  }

  // Conveyor structure: rollers and moving belt marks provide motion while products wait for pickup.
  var belt = new T.Group(); world.add(belt);
  var beltCenter = new T.Vector3(-1.68, .59, -1.48);
  box(belt, [4.45, .15, 1.48], [beltCenter.x, .42, beltCenter.z], mats.darkSteel);
  box(belt, [4.22, .08, 1.3], [beltCenter.x, .535, beltCenter.z], mats.belt);
  box(belt, [4.35, .1, .09], [beltCenter.x, .59, beltCenter.z - .72], mats.steel);
  box(belt, [4.35, .1, .09], [beltCenter.x, .59, beltCenter.z + .72], mats.steel);
  var rollers = [];
  for (var ri = 0; ri < 16; ri++) {
    var rollerX = -3.72 + ri * .275;
    var roller = cylinder(belt, .075, .075, 1.28, [rollerX, .61, beltCenter.z], mats.silver, 12);
    roller.rotation.x = Math.PI / 2; rollers.push(roller);
  }
  for (var legX of [-3.35, -.1]) for (var legZ of [-1.95, -1.02]) {
    box(world, [.13, .41, .13], [legX, .18, legZ], mats.steel);
    box(world, [.36, .05, .36], [legX, -.015, legZ], mats.darkSteel);
  }
  box(belt, [.14, .39, 1.48], [.54, .76, beltCenter.z], mats.orange);
  box(belt, [.08, .25, 1.05], [.445, .91, beltCenter.z], mats.black);
  var stopX = .22, conveyorEntryX = -3.76, conveyorSpeed = 1.15, itemSpacing = .62;
  box(belt, [.075, .018, 1.2], [stopX, .59, beltCenter.z], mats.orange);
  cylinder(world, .055, .055, .055, [stopX, 1.45, beltCenter.z - .58], mats.cyan, 12);
  cylinder(world, .055, .055, .055, [stopX, 1.45, beltCenter.z + .58], mats.cyan, 12);
  box(world, [.035, 1.68, .035], [stopX, .62, beltCenter.z - .58], mats.steel);
  box(world, [.035, 1.68, .035], [stopX, .62, beltCenter.z + .58], mats.steel);
  var stopPlane = new T.Mesh(new T.PlaneGeometry(1.14, 1.55), new T.MeshBasicMaterial({ color: 0x63dece, transparent: true, opacity: .075, side: T.DoubleSide, depthWrite: false }));
  stopPlane.rotation.y = Math.PI / 2; stopPlane.position.set(stopX, .95, beltCenter.z); world.add(stopPlane);
  var stopLabel = label("PICK / STOP", "#f4a463"); stopLabel.scale.set(.85, .2, 1); stopLabel.position.set(stopX, 1.88, beltCenter.z - .02); world.add(stopLabel);
  var beltTicks = [];
  for (var ti = 0; ti < 11; ti++) beltTicks.push(box(belt, [.025, .014, 1.16], [-3.62 + ti * .39, .589, beltCenter.z], mats.cyan));
  var inLabel = label("INBOUND / 01", "#8de5d8"); inLabel.position.set(-1.65, 1.35, -2.36); world.add(inLabel);

  // Product cartons; a successful close near a carton attaches it to the gripper.
  var products = [];
  function makeProduct(color, code) {
    var group = new T.Group(); group.position.set(conveyorEntryX, .81, beltCenter.z); group.visible = false; world.add(group);
    var carton = new T.Mesh(new T.BoxGeometry(.39, .38, .34), mat(color, .55, .02)); carton.position.y = 0; group.add(carton);
    box(group, [.405, .035, .36], [0, .08, 0], mats.white);
    box(group, [.24, .02, .026], [0, .12, .168], mats.orange);
    var tag = label(code, "#dce9e8"); tag.scale.set(.48, .12, 1); tag.position.set(0, .23, .01); group.add(tag);
    products.push({ group: group, status: "waiting", available: false, code: code, stopX: stopX });
  }
  makeProduct(0x758fc2, "BOX / 01");
  makeProduct(0xc48552, "BOX / 02");
  makeProduct(0x668f83, "BOX / 03");
  var nextProductIndex = 0, movingProduct = null, nextReleaseIn = 0;
  function releaseNextProduct() {
    if (movingProduct || nextProductIndex >= products.length) return;
    var product = products[nextProductIndex++];
    product.group.visible = true; product.group.position.set(conveyorEntryX, .81, beltCenter.z);
    product.group.rotation.set(0, 0, 0); product.status = "moving"; product.available = false;
    movingProduct = product;
  }
  function advanceConveyor(dt) {
    if (movingProduct) {
      var nextStopX = stopX;
      products.forEach(function (other) {
        if (other === movingProduct || other.status !== "stopped") return;
        nextStopX = Math.min(nextStopX, other.group.position.x - itemSpacing);
      });
      movingProduct.group.position.x = Math.min(nextStopX, movingProduct.group.position.x + conveyorSpeed * dt);
      movingProduct.stopX = nextStopX;
      if (movingProduct.group.position.x >= nextStopX - .002) {
        movingProduct.group.position.x = nextStopX;
        movingProduct.status = "stopped";
        movingProduct.available = Math.abs(nextStopX - stopX) < .04;
        movingProduct = null; nextReleaseIn = .72;
      }
    } else {
      var queued = products.filter(function (p) { return p.status === "stopped" && p.group.position.x < stopX - .04; })
        .sort(function (a, b) { return b.group.position.x - a.group.position.x; })[0];
      if (queued) {
        queued.status = "moving"; queued.available = false; movingProduct = queued;
      } else if (nextProductIndex < products.length) {
        nextReleaseIn -= dt;
        if (nextReleaseIn <= 0) releaseNextProduct();
      }
    }
  }
  var heldProduct = null;

  // Collection basket with open top and reinforced wire-like rails.
  var basket = new T.Group(); world.add(basket); basket.position.set(1.53, 0, .85);
  var bw = 1.15, bd = .94, bh = .82;
  box(basket, [bw, .11, bd], [0, .19, 0], mats.basket);
  var railY = .63;
  [[0, railY, -bd / 2], [0, railY, bd / 2]].forEach(function (p) { box(basket, [bw, .07, .07], p, mats.cyan); });
  [[-bw / 2, railY, 0], [bw / 2, railY, 0]].forEach(function (p) { box(basket, [.07, .07, bd], p, mats.cyan); });
  for (var bx of [-bw / 2, bw / 2]) for (var bz of [-bd / 2, bd / 2]) box(basket, [.07, bh, .07], [bx, .4, bz], mats.steel);
  for (var wire = 1; wire <= 4; wire++) {
    var wy = .19 + wire * .13;
    box(basket, [bw, .018, .018], [0, wy, -bd / 2], mats.steel);
    box(basket, [bw, .018, .018], [0, wy, bd / 2], mats.steel);
    box(basket, [.018, .018, bd], [-bw / 2, wy, 0], mats.steel);
    box(basket, [.018, .018, bd], [bw / 2, wy, 0], mats.steel);
  }
  box(basket, [.66, .23, .06], [0, .51, bd / 2 + .035], mats.darkSteel);
  var basketTag = label("TARGET / BIN", "#8de5d8"); basketTag.scale.set(.77, .19, 1); basketTag.position.set(0, .52, bd / 2 + .072); basket.add(basketTag);
  var outLabel = label("OUTBOUND / 02", "#8de5d8"); outLabel.position.set(1.55, 1.08, 1.56); world.add(outLabel);
  var basketGoods = new T.Group(); basket.add(basketGoods);
  var basketCount = 0;

  // Industrial arm. Link endpoints are solved from a Cartesian target using a two-link planar IK model.
  var arm = new T.Group(); world.add(arm);
  box(arm, [1.12, .18, 1.12], [0, .14, 0], mats.darkSteel);
  cylinder(arm, .58, .64, .2, [0, .29, 0], mats.steel, 28);
  cylinder(arm, .43, .43, .22, [0, .5, 0], mats.arm, 28);
  cylinder(arm, .34, .38, .39, [0, .77, 0], mats.armDark, 24);
  cylinder(arm, .3, .31, .14, [0, .99, 0], mats.arm, 24);
  var shoulder = new T.Vector3(0, 1.22, 0), upperLength = 1.34, lowerLength = 1.34;
  var jointMat = mat(0x43545a, .34, .7);
  var shoulderJoint = new T.Mesh(new T.SphereGeometry(.27, 20, 14), mats.arm); arm.add(shoulderJoint);
  var elbowJoint = new T.Mesh(new T.SphereGeometry(.19, 18, 12), mats.arm); arm.add(elbowJoint);
  var wristJoint = new T.Mesh(new T.SphereGeometry(.14, 16, 10), mats.cyan); arm.add(wristJoint);
  var upper = new T.Mesh(new T.CylinderGeometry(.145, .21, 1, 18), mats.arm); arm.add(upper);
  var lower = new T.Mesh(new T.CylinderGeometry(.105, .145, 1, 18), mats.armDark); arm.add(lower);
  var upperBand = new T.Mesh(new T.TorusGeometry(.16, .026, 6, 16).rotateX(Math.PI / 2), mats.cyan); arm.add(upperBand);
  var lowerBand = new T.Mesh(new T.TorusGeometry(.117, .022, 6, 16).rotateX(Math.PI / 2), mats.orange); arm.add(lowerBand);
  var endTool = new T.Group(); world.add(endTool);
  cylinder(endTool, .12, .14, .12, [0, .06, 0], mats.silver, 16);
  box(endTool, [.36, .1, .28], [0, -.04, 0], mats.darkSteel);
  var jawA = box(endTool, [.085, .27, .11], [-.19, -.19, 0], mats.cyan);
  var jawB = box(endTool, [.085, .27, .11], [.19, -.19, 0], mats.cyan);
  var targetDot = new T.Mesh(new T.TorusGeometry(.19, .018, 6, 36), new T.MeshBasicMaterial({ color: 0x6ce1d0, transparent: true, opacity: .7 }));
  targetDot.rotation.x = Math.PI / 2; world.add(targetDot);
  var targetBeam = new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(0, .04, 0), new T.Vector3(0, 1, 0)]), new T.LineBasicMaterial({ color: 0x6ce1d0, transparent: true, opacity: .35 }));
  targetBeam.frustumCulled = false; world.add(targetBeam);
  var lightBase = new T.PointLight(0x62dbc8, 1.7, 2.5, 2); arm.add(lightBase); lightBase.position.set(0, 1.5, .15);

  // Simple labels and a virtual camera marker reinforce the perception-to-actuation flow.
  var camRig = new T.Group(); world.add(camRig); camRig.position.set(-3.95, 2.38, 1.1);
  box(camRig, [.46, .31, .38], [0, 0, 0], mats.black);
  cylinder(camRig, .13, .13, .12, [0, 0, .23], mats.cyan, 16).rotation.x = Math.PI / 2;
  box(camRig, [.75, .06, .08], [.17, -.23, 0], mats.steel);
  var cameraLabel = label("KEYPOINT INPUT", "#8de5d8"); cameraLabel.scale.set(1.02, .25, 1); cameraLabel.position.set(-3.82, 2.78, 1.1); world.add(cameraLabel);
  line(world, [[-3.72, 2.26, 1.3], [-3.15, 1.78, .6], [-2.25, 1.24, -.35]], 0x62dbc8, .45);

  // Soft holographic target plane and floor anchors.
  var workRing = new T.Mesh(new T.TorusGeometry(2.35, .012, 4, 96), new T.MeshBasicMaterial({ color: 0x719092, transparent: true, opacity: .24 }));
  workRing.rotation.x = Math.PI / 2; workRing.position.set(0, .018, 0); world.add(workRing);

  function setSegment(mesh, a, b) {
    var vector = new T.Vector3().subVectors(b, a), length = vector.length();
    mesh.position.copy(a).add(b).multiplyScalar(.5); mesh.scale.y = length;
    mesh.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), vector.normalize());
  }
  var currentTarget = new T.Vector3(-.2, 2.08, .12), commandedTarget = currentTarget.clone();
  var currentGrip = 0, commandedGrip = 0, lastSequence = 0, apiOnline = false, demo = null;
  var armYaw = 0;
  function solveArm() {
    var dx = currentTarget.x - shoulder.x, dz = currentTarget.z - shoulder.z;
    var rho = Math.max(.001, Math.hypot(dx, dz)), dy = currentTarget.y - shoulder.y;
    var distance = Math.max(.08, Math.min(upperLength + lowerLength - .002, Math.hypot(rho, dy)));
    var cosA = T.MathUtils.clamp((upperLength * upperLength + distance * distance - lowerLength * lowerLength) / (2 * upperLength * distance), -1, 1);
    var angleA = Math.acos(cosA), direction = Math.atan2(dy, rho), shoulderPitch = direction + angleA;
    var reach = upperLength * Math.cos(shoulderPitch), rise = upperLength * Math.sin(shoulderPitch);
    var yaw = Math.atan2(dz, dx); armYaw += Math.atan2(Math.sin(yaw - armYaw), Math.cos(yaw - armYaw)) * .22;
    var elbow = new T.Vector3(shoulder.x + Math.cos(armYaw) * reach, shoulder.y + rise, shoulder.z + Math.sin(armYaw) * reach);
    shoulderJoint.position.copy(shoulder); elbowJoint.position.copy(elbow); wristJoint.position.copy(currentTarget);
    setSegment(upper, shoulder, elbow); setSegment(lower, elbow, currentTarget);
    upperBand.position.copy(shoulder).lerp(elbow, .42); upperBand.quaternion.copy(upper.quaternion);
    lowerBand.position.copy(elbow).lerp(currentTarget, .32); lowerBand.quaternion.copy(lower.quaternion);
    endTool.position.set(currentTarget.x, currentTarget.y, currentTarget.z); endTool.rotation.y = -armYaw;
    var opening = .39 * (1 - currentGrip) + .08 * currentGrip;
    jawA.position.x = -opening; jawB.position.x = opening;
    targetDot.position.set(commandedTarget.x, .028, commandedTarget.z);
    var beamPoints = targetBeam.geometry.attributes.position;
    beamPoints.setXYZ(0, currentTarget.x, .04, currentTarget.z); beamPoints.setXYZ(1, currentTarget.x, currentTarget.y, currentTarget.z); beamPoints.needsUpdate = true;
    if (heldProduct) heldProduct.group.position.set(currentTarget.x, currentTarget.y - .19, currentTarget.z);
  }

  function updateTelemetry() {
    $("coord-x").innerHTML = currentTarget.x.toFixed(2) + " <small>m</small>";
    $("coord-y").innerHTML = currentTarget.y.toFixed(2) + " <small>m</small>";
    $("coord-z").innerHTML = currentTarget.z.toFixed(2) + " <small>m</small>";
    var closed = currentGrip > .55;
    $("grip-state").textContent = closed ? "ĐÓNG" : "MỞ";
    $("grip-led").classList.toggle("closed", closed);
  }
  function updateStatus(label, detail, busy) {
    $("run-state").textContent = label; $("run-detail").textContent = detail;
    $("status-icon").classList.toggle("busy", !!busy);
    $("state-tag").textContent = busy ? "ACTIVE" : (apiOnline ? "READY" : "OFFLINE");
  }
  var toastTimer;
  function showToast(message) {
    var el = $("toast"); el.textContent = message; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { el.classList.remove("show"); }, 2600);
  }
  function captureProduct() {
    if (heldProduct || currentGrip < .68) return;
    var best = null, bestDistance = 1e9;
    products.forEach(function (product) {
      if (!product.available || product.status !== "stopped") return;
      var p = product.group.position;
      var distance = Math.hypot(p.x - currentTarget.x, p.z - currentTarget.z);
      if (distance < bestDistance) { best = product; bestDistance = distance; }
    });
    if (best && bestDistance < .48 && Math.abs(currentTarget.y - .98) < .55) {
      heldProduct = best; heldProduct.available = false; heldProduct.status = "held";
      showToast("Đã gắp " + heldProduct.code.toLowerCase());
    }
  }
  function releaseProduct() {
    if (!heldProduct) return;
    var product = heldProduct; heldProduct = null; product.status = "basket";
    basketCount++;
    var slot = basketCount - 1, positions = [[-.24, -.16], [.22, -.12], [-.03, .2]];
    var place = positions[slot % positions.length];
    product.group.position.set(basket.position.x + place[0], .48 + Math.floor(slot / 3) * .35, basket.position.z + place[1]);
    product.group.rotation.y = (slot % 2) * .22 - .11;
    showToast("Đã đặt hàng vào giỏ · " + basketCount + " sản phẩm");
  }

  // The demonstration follows the same target/grip interface as an external controller.
  var demoSteps = [];
  function makeDemoSteps() {
    demoSteps = [];
    products.forEach(function (product, index) {
      var x = stopX, z = beltCenter.z, bx = basket.position.x + (index - 1) * .16, bz = basket.position.z;
      demoSteps.push({ waitFor: product, ms: 0 });
      demoSteps.push({ target: [x, 1.36, z], grip: 0, ms: 580 });
      demoSteps.push({ target: [x, .99, z], grip: 0, ms: 500 });
      demoSteps.push({ target: [x, .99, z], grip: 1, ms: 360 });
      demoSteps.push({ target: [x, 1.72, z], grip: 1, ms: 530 });
      demoSteps.push({ target: [bx, 1.72, bz], grip: 1, ms: 720 });
      demoSteps.push({ target: [bx, 1.15, bz], grip: 1, ms: 480 });
      demoSteps.push({ target: [bx, 1.15, bz], grip: 0, ms: 360 });
      demoSteps.push({ target: [0, 2.08, 0], grip: 0, ms: 520 });
    });
  }
  function startDemo() {
    if (demo) return;
    resetProducts(); makeDemoSteps(); demo = { index: 0, elapsed: 0, from: currentTarget.clone(), fromGrip: currentGrip };
    $("demo-button").disabled = true;
    updateStatus("Đang chạy demo", "Robot đang gắp sản phẩm từ băng chuyền", true);
  }
  function resetProducts() {
    heldProduct = null;
    products.forEach(function (p) {
      p.group.position.set(conveyorEntryX, .81, beltCenter.z); p.group.rotation.set(0, 0, 0);
      p.group.visible = false; p.available = false; p.status = "waiting"; p.stopX = stopX;
    });
    nextProductIndex = 0; movingProduct = null; nextReleaseIn = 0; basketCount = 0;
  }
  function stopDemo() { demo = null; $("demo-button").disabled = false; }
  function resetArm() {
    stopDemo(); resetProducts(); commandedTarget.set(-.2, 2.08, .12); commandedGrip = 0;
    updateStatus("Đang chờ lệnh", apiOnline ? "Gửi lệnh qua API để di chuyển robot" : "Khởi động bridge để nhận lệnh", false);
  }
  $("demo-button").addEventListener("click", startDemo);
  $("reset-button").addEventListener("click", resetArm);
  $("contract-toggle").addEventListener("click", function () {
    var open = this.getAttribute("aria-expanded") === "true";
    this.setAttribute("aria-expanded", String(!open)); $("contract").hidden = open;
    this.querySelector("span").textContent = open ? "＋" : "−";
  });

  function applyCommand(command) {
    if (!command || !command.target) return;
    stopDemo();
    commandedTarget.set(command.target.x, command.target.y, command.target.z);
    commandedGrip = command.grip ? 1 : 0;
    $("demo-button").disabled = false;
    updateStatus("Đã nhận lệnh", "Đang theo dõi mục tiêu đầu kẹp", true);
  }
  async function pollCommands() {
    try {
      var response = await fetch("/api/command?after=" + lastSequence, { cache: "no-store" });
      if (!response.ok) throw new Error("bridge offline");
      var body = await response.json();
      if (!apiOnline) {
        apiOnline = true; $("connection").textContent = "BRIDGE SẴN SÀNG"; document.querySelector(".live-dot").classList.remove("offline");
        if (!demo) updateStatus("Đang chờ lệnh", "Gửi lệnh qua API để di chuyển robot", false);
      }
      if (body.command && body.sequence > lastSequence) { lastSequence = body.sequence; applyCommand(body.command); }
    } catch (_) {
      apiOnline = false; $("connection").textContent = "BRIDGE NGOẠI TUYẾN"; document.querySelector(".live-dot").classList.add("offline");
      if (!demo) updateStatus("Chưa kết nối bridge", "Chạy python simulation/serve.py để nhận lệnh", false);
    }
    window.setTimeout(pollCommands, 26);
  }
  fetch("/api/health", { cache: "no-store" }).catch(function () {});
  pollCommands();

  function updateDemo(dt) {
    if (!demo) return;
    var step = demoSteps[demo.index];
    if (!step) {
      stopDemo(); updateStatus("Demo hoàn tất", "Đã chuyển " + basketCount + " sản phẩm vào giỏ", false); return;
    }
    if (step.waitFor) {
      if (step.waitFor.status !== "stopped" || Math.abs(step.waitFor.group.position.x - stopX) >= .04) return;
      demo.index++; demo.elapsed = 0; demo.from.copy(commandedTarget); demo.fromGrip = commandedGrip;
      return;
    }
    demo.elapsed += dt * 1000;
    var u = T.MathUtils.clamp(demo.elapsed / step.ms, 0, 1), eased = u * u * (3 - 2 * u);
    commandedTarget.set(demo.from.x + (step.target[0] - demo.from.x) * eased, demo.from.y + (step.target[1] - demo.from.y) * eased, demo.from.z + (step.target[2] - demo.from.z) * eased);
    commandedGrip = demo.fromGrip + (step.grip - demo.fromGrip) * eased;
    if (u >= 1) {
      demo.index++; demo.elapsed = 0; demo.from.copy(commandedTarget); demo.fromGrip = commandedGrip;
    }
  }

  function updateCamera() {
    var cp = Math.cos(view.pitch);
    camera.position.set(focus.x + view.distance * cp * Math.cos(view.yaw), focus.y + view.distance * Math.sin(view.pitch), focus.z + view.distance * cp * Math.sin(view.yaw));
    camera.lookAt(focus);
  }
  updateCamera();
  renderer.domElement.addEventListener("pointerdown", function (e) { pointer.down = true; pointer.x = e.clientX; pointer.y = e.clientY; renderer.domElement.setPointerCapture(e.pointerId); });
  renderer.domElement.addEventListener("pointermove", function (e) {
    if (!pointer.down) return;
    view.yaw += (e.clientX - pointer.x) * .006; view.pitch = T.MathUtils.clamp(view.pitch + (pointer.y - e.clientY) * .005, .08, 1.27);
    pointer.x = e.clientX; pointer.y = e.clientY;
  });
  function pointerUp() { pointer.down = false; }
  renderer.domElement.addEventListener("pointerup", pointerUp); renderer.domElement.addEventListener("pointercancel", pointerUp);
  renderer.domElement.addEventListener("wheel", function (e) { e.preventDefault(); view.distance = T.MathUtils.clamp(view.distance * Math.exp(e.deltaY * .001), 6.2, 17); }, { passive: false });
  renderer.domElement.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  window.addEventListener("resize", function () {
    var width = stage.clientWidth, height = Math.max(1, stage.clientHeight);
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
  });

  solveArm();
  function frame() {
    requestAnimationFrame(frame);
    var dt = Math.min(clock.getDelta(), .05);
    advanceConveyor(dt);
    updateDemo(dt);
    var alpha = 1 - Math.exp(-dt * 17);
    currentTarget.lerp(commandedTarget, alpha); currentGrip += (commandedGrip - currentGrip) * (1 - Math.exp(-dt * 14));
    solveArm(); captureProduct();
    if (heldProduct && currentGrip < .25) releaseProduct();
    for (var i = 0; i < rollers.length; i++) rollers[i].rotation.z += dt * 2.3;
    beltTicks.forEach(function (tick) { tick.position.x += dt * .28; if (tick.position.x > .49) tick.position.x = -3.72; });
    targetDot.rotation.z += dt * .25; targetDot.material.opacity = .52 + Math.sin(performance.now() * .003) * .12;
    updateCamera(); updateTelemetry(); renderer.render(scene, camera);
  }
  frame();
  requestAnimationFrame(function () { $("loading").classList.add("done"); });
})();
