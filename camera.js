// DarahBot photo booth camera (v3)
// ONE PHOTO
//  * phone / iPad / Android: the device's own Camera app opens straight away (portrait or landscape, as held)
//  * laptop / desktop: full-screen webcam, always LANDSCAPE, 3-2-1 countdown
// PHOTO BOOTH (4 photos)
//  * every device: full-screen camera, a warning first, then ONE press starts the timer and
//    4 photos are taken in a row (3 seconds before each), without closing the camera.
// Front camera / webcam is MIRRORED like a mirror, and the saved photo is mirrored the same way,
// so the photo looks exactly like what you saw on screen (back camera: not mirrored).
(function () {
  if (window.__dbCam5) return;
  window.__dbCam5 = true;
  const SEL = '[class*="st-key-cam"]';
  const touch = (window.matchMedia && matchMedia('(pointer: coarse)').matches) || navigator.maxTouchPoints > 1;
  const isBooth = function (box) { return /st-key-cambooth/.test(box.className); };

  // 1) single-photo boxes on phones/iPads open the Camera app directly
  function prep() {
    document.querySelectorAll(SEL).forEach(function (box) {
      const inp = box.querySelector('input[type=file]');
      if (!inp || inp.dataset.dbcam) return;
      inp.dataset.dbcam = '1';
      inp.setAttribute('accept', 'image/*');
      if (touch && !isBooth(box)) inp.setAttribute('capture', 'user');
    });
  }
  new MutationObserver(prep).observe(document.body, { childList: true, subtree: true });
  prep();

  const css = document.createElement('style');
  css.textContent = `
  #dbcam{position:fixed;inset:0;z-index:999999;background:#140306;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:12px;box-sizing:border-box;font-family:Inter,system-ui,sans-serif;animation:dbIn .3s ease both}
  @keyframes dbIn{from{opacity:0}to{opacity:1}}
  #dbcam .title{color:#fff;font:800 22px 'Bricolage Grotesque',Inter,sans-serif;text-align:center}
  #dbcam .stage{position:relative;max-width:94vw;max-height:66vh;border-radius:22px;overflow:hidden;background:#000;box-shadow:0 30px 80px -20px rgba(216,31,59,.45)}
  #dbcam .stage.land{width:min(94vw,calc(66vh*16/9));aspect-ratio:16/9}
  #dbcam video,#dbcam .stage>img{width:100%;height:100%;object-fit:cover;display:block}
  #dbcam video.mirror{transform:scaleX(-1)}
  #dbcam .count{position:absolute;inset:0;display:grid;place-items:center;font:800 min(26vh,200px)/1 'Bricolage Grotesque',Inter,sans-serif;color:#fff;text-shadow:0 10px 40px rgba(0,0,0,.6);pointer-events:none}
  #dbcam .badge{position:absolute;left:14px;top:14px;background:#B0122A;color:#fff;font:800 16px Inter,sans-serif;padding:8px 14px;border-radius:999px;display:none}
  #dbcam .flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none}
  #dbcam .flash.go{animation:dbFlash .45s ease}
  @keyframes dbFlash{0%{opacity:.95}100%{opacity:0}}
  #dbcam .thumbs{display:flex;gap:8px;min-height:0}
  #dbcam .thumbs img{height:58px;border-radius:8px;border:2px solid #fff;animation:dbIn .3s ease both}
  #dbcam .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;max-width:min(94vw,900px)}
  #dbcam .grid img{width:100%;max-height:30vh;object-fit:contain;border-radius:12px;border:3px solid #fff;background:#000}
  #dbcam .bar{display:flex;gap:12px;flex-wrap:wrap;justify-content:center}
  #dbcam button{border:0;border-radius:999px;padding:14px 26px;font:700 16px Inter,system-ui,sans-serif;cursor:pointer;background:rgba(255,255,255,.12);color:#fff}
  #dbcam button.main{background:linear-gradient(180deg,#E8283F,#B0122A);padding:16px 34px;font-size:18px;box-shadow:0 12px 30px -10px rgba(216,31,59,.9)}
  #dbcam .msg{color:#fff;opacity:.9;text-align:center;max-width:620px;line-height:1.5}
  #dbcam .warn{background:#fff;color:#2B0F13;border-radius:18px;padding:16px 20px;max-width:560px;text-align:center;line-height:1.5;box-shadow:0 20px 50px -20px rgba(216,31,59,.7)}
  #dbcam .warn b{color:#B0122A;font-size:19px;display:block;margin-bottom:4px}
  #dbcam .warn small{color:#8D7476;display:block;margin-top:6px}`;
  document.head.appendChild(css);

  let stream = null, facing = 'user', devices = [], devIdx = 0;
  // front camera / laptop webcam: mirrored like a mirror, and the SAVED photo is mirrored the same way
  const mirrored = function () { return !touch || facing === 'user'; };
  const sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  function stop() { if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; } }
  function close() { stop(); const o = document.getElementById('dbcam'); if (o) o.remove(); }

  async function start(video, stage, msg) {
    stop();
    try {
      let v;
      if (touch) {
        v = { facingMode: facing, width: { ideal: 3840 }, height: { ideal: 2160 } };
      } else {
        // computers: always landscape; prefer the built-in camera over a phone used as a webcam
        if (!devices.length) {
          const tmp = await navigator.mediaDevices.getUserMedia({ video: true });
          tmp.getTracks().forEach(function (t) { t.stop(); });
          const all = (await navigator.mediaDevices.enumerateDevices()).filter(function (d) { return d.kind === 'videoinput'; });
          const builtIn = all.filter(function (d) { return !/iphone|ipad|continuity|desk view/i.test(d.label); });
          devices = builtIn.concat(all.filter(function (d) { return builtIn.indexOf(d) < 0; }));
        }
        v = { width: { ideal: 1920 }, height: { ideal: 1080 }, aspectRatio: { ideal: 16 / 9 } };
        if (devices[devIdx]) v.deviceId = { exact: devices[devIdx].deviceId };
      }
      stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: v });
      video.srcObject = stream;
      await video.play();
      video.classList.toggle('mirror', mirrored());   // selfie view, like a mirror
      if (touch) {
        stage.classList.remove('land');
        stage.style.aspectRatio = video.videoWidth + '/' + video.videoHeight;
        stage.style.width = 'min(94vw, calc(66vh * ' + (video.videoWidth / video.videoHeight) + '))';
      } else {
        stage.classList.add('land');
      }
      return true;
    } catch (e) {
      msg.textContent = 'Camera not available. Please allow camera access in the browser, then try again. · Kamera tidak dapat dibuka. Benarkan akses kamera dalam pelayar.';
      return false;
    }
  }

  // one frame from the camera, mirrored like the preview; on computers always cut to 16:9 landscape
  function grab(video) {
    let sw = video.videoWidth, sh = video.videoHeight, sx = 0, sy = 0;
    if (!touch && sw / sh < 16 / 9 - 0.01) {           // e.g. an iPhone held upright as the Mac's camera
      const h = Math.round(sw * 9 / 16);
      sy = Math.round((sh - h) * 0.4); sh = h;
    }
    const c = document.createElement('canvas');
    c.width = sw; c.height = sh;
    const g = c.getContext('2d');
    if (mirrored()) { g.translate(sw, 0); g.scale(-1, 1); }   // keep it exactly as seen on screen
    g.drawImage(video, sx, sy, sw, sh, 0, 0, sw, sh);
    return c;
  }
  const toBlob = function (c) { return new Promise(function (r) { c.toBlob(r, 'image/jpeg', 0.93); }); };

  async function countdown(count, flash, n) {
    for (let k = n; k >= 1; k--) { count.textContent = k; await sleep(900); }
    count.textContent = '';
    flash.classList.remove('go'); void flash.offsetWidth; flash.classList.add('go');
  }

  async function deliver(inp, canvases) {
    const dt = new DataTransfer();
    for (let i = 0; i < canvases.length; i++) {
      const b = await toBlob(canvases[i]);
      dt.items.add(new File([b], 'darahbot-' + (i + 1) + '-' + Date.now() + '.jpg', { type: 'image/jpeg' }));
    }
    inp.files = dt.files;
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    close();
  }

  function open(inp, booth) {
    close();
    const o = document.createElement('div');
    o.id = 'dbcam';
    o.innerHTML = '<div class="title">' + (booth ? '🎞️ DarahBot photo booth · 4 photos' : '📸 DarahBot photo') + '</div>' +
      '<div class="stage land"><video playsinline muted></video><div class="badge"></div><div class="count"></div><div class="flash"></div></div>' +
      '<div class="thumbs"></div><div class="msg">Opening the camera… · Membuka kamera…</div><div class="bar"></div>';
    document.body.appendChild(o);
    const video = o.querySelector('video'), stage = o.querySelector('.stage'), msg = o.querySelector('.msg');
    const count = o.querySelector('.count'), flash = o.querySelector('.flash'), bar = o.querySelector('.bar');
    const badge = o.querySelector('.badge'), thumbs = o.querySelector('.thumbs');

    function controls(mainLabel, onMain) {
      bar.innerHTML = '<button class="cancel">✕ Cancel · Batal</button>' +
        ((touch || devices.length > 1) ? '<button class="flip">🔄 Switch camera</button>' : '') +
        '<button class="main go">' + mainLabel + '</button>';
      bar.querySelector('.cancel').onclick = close;
      const f = bar.querySelector('.flip');
      if (f) f.onclick = async function () {
        if (touch) facing = facing === 'user' ? 'environment' : 'user'; else devIdx = (devIdx + 1) % devices.length;
        await start(video, stage, msg);
      };
      bar.querySelector('.go').onclick = onMain;
    }

    function review(canvases) {
      stop();
      if (booth) {
        stage.style.display = 'none'; thumbs.innerHTML = '';
        const g = document.createElement('div'); g.className = 'grid';
        canvases.forEach(function (c) { const im = document.createElement('img'); im.src = c.toDataURL('image/jpeg', .8); g.appendChild(im); });
        msg.before(g);
      } else {
        video.replaceWith(Object.assign(document.createElement('img'), { src: canvases[0].toDataURL('image/jpeg', .9) }));
      }
      msg.textContent = 'Happy with ' + (booth ? 'them' : 'it') + '? · Puas hati?';
      bar.innerHTML = '<button class="retake">↺ Retake · Ambil semula</button><button class="main use">✓ Use ' + (booth ? 'these photos' : 'this photo') + ' · Guna</button>';
      bar.querySelector('.retake').onclick = function () { open(inp, booth); };
      bar.querySelector('.use').onclick = function () { deliver(inp, canvases); };
    }

    (async function () {
      const ok = await start(video, stage, msg);
      if (!ok) { bar.innerHTML = '<button class="cancel">✕ Close · Tutup</button>'; bar.querySelector('.cancel').onclick = close; return; }
      if (!booth) {
        msg.textContent = 'Smile! Press the red button. · Senyum! Tekan butang merah.';
        controls('📸 Take photo · Ambil gambar', async function () {
          bar.style.visibility = 'hidden';
          await countdown(count, flash, 3);
          const c = grab(video);
          bar.style.visibility = 'visible';
          review([c]);
        });
        return;
      }
      // photo booth: warn first, then one press = 4 photos in a row
      msg.innerHTML = '<div class="warn"><b>Heads up! 4 photos in a row</b>After you press Start, a 3-second timer runs before EACH photo. ' +
        'The camera keeps going until all 4 are taken, so change your pose each time!' +
        '<small>Perhatian! Mod ini mengambil 4 gambar berturut-turut. Pemasa 3 saat sebelum setiap gambar. Tukar gaya setiap kali!</small></div>';
      controls('▶ Start · Mula', async function () {
        bar.style.visibility = 'hidden';
        msg.textContent = 'Get ready! · Bersedia!';
        badge.style.display = 'block';
        const shots = [];
        for (let i = 1; i <= 4; i++) {
          badge.textContent = 'Photo ' + i + ' / 4';
          msg.textContent = i === 1 ? 'Get ready! · Bersedia!' : 'Next pose! · Gaya seterusnya!';
          await countdown(count, flash, 3);
          const c = grab(video);
          shots.push(c);
          const t = document.createElement('img'); t.src = c.toDataURL('image/jpeg', .6); thumbs.appendChild(t);
          await sleep(700);
        }
        badge.style.display = 'none';
        bar.style.visibility = 'visible';
        review(shots);
      });
    })();
  }

  // clicks on a camera box: booth -> our 4-photo camera on every device; single -> our camera on computers only
  window.addEventListener('click', function (e) {
    const box = e.target.closest && e.target.closest(SEL);
    if (!box || e.target.closest('[data-testid="stFileChipDeleteBtn"]')) return;
    if (!e.target.closest('[data-testid="stFileUploaderDropzone"], [data-testid="stFileUploader"] button, [data-testid="stFileUploader"] section')) return;
    const booth = isBooth(box);
    if (touch && !booth) return;                      // phones/iPads: native Camera app
    const inp = box.querySelector('input[type=file]');
    if (!inp) return;
    e.preventDefault(); e.stopPropagation();
    open(inp, booth);
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
})();
