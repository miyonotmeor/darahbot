// DarahBot photo booth camera.
// Turns the photo boxes in the memory section into CAMERA buttons:
//  * phone / iPad / Android: opens the device's own Camera app straight away (full quality, its own settings)
//  * laptop / desktop: opens the webcam full screen at its highest resolution, with a 3-2-1 countdown
// The captured picture is handed back to the app, which adds the DarahBot frame automatically.
(function () {
  if (window.__dbCam) return;
  window.__dbCam = true;
  const SEL = '[class*="st-key-cam"]';
  const touch = (window.matchMedia && matchMedia('(pointer: coarse)').matches) || navigator.maxTouchPoints > 1;

  // 1) every camera box: images only, and open the camera app directly on touch devices
  function prep() {
    document.querySelectorAll(SEL + ' input[type=file]').forEach(function (inp) {
      if (inp.dataset.dbcam) return;
      inp.dataset.dbcam = '1';
      inp.setAttribute('accept', 'image/*');
      if (touch) inp.setAttribute('capture', 'user');
    });
  }
  new MutationObserver(prep).observe(document.body, { childList: true, subtree: true });
  prep();
  if (touch) return;   // phones and tablets use their own camera app, nothing more to do

  // 2) computers: our own full-screen camera instead of the "choose a file" window
  const css = document.createElement('style');
  css.textContent = `
  #dbcam{position:fixed;inset:0;z-index:999999;background:#140306;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;font-family:Inter,system-ui,sans-serif;animation:dbIn .3s ease both}
  @keyframes dbIn{from{opacity:0}to{opacity:1}}
  #dbcam .stage{position:relative;width:min(92vw,calc(78vh*16/9));aspect-ratio:16/9;border-radius:22px;overflow:hidden;background:#000;box-shadow:0 30px 80px -20px rgba(216,31,59,.45)}
  #dbcam video,#dbcam img{width:100%;height:100%;object-fit:contain;display:block}
  #dbcam video.mirror{transform:scaleX(-1)}
  #dbcam .count{position:absolute;inset:0;display:grid;place-items:center;font:800 min(30vh,220px)/1 'Bricolage Grotesque',Inter,sans-serif;color:#fff;text-shadow:0 10px 40px rgba(0,0,0,.6);pointer-events:none}
  #dbcam .flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none}
  #dbcam .flash.go{animation:dbFlash .45s ease}
  @keyframes dbFlash{0%{opacity:.95}100%{opacity:0}}
  #dbcam .bar{display:flex;gap:12px;flex-wrap:wrap;justify-content:center}
  #dbcam button{border:0;border-radius:999px;padding:14px 26px;font:700 16px Inter,system-ui,sans-serif;cursor:pointer;background:rgba(255,255,255,.12);color:#fff}
  #dbcam button.main{background:linear-gradient(180deg,#E8283F,#B0122A);padding:16px 34px;font-size:18px;box-shadow:0 12px 30px -10px rgba(216,31,59,.9)}
  #dbcam .msg{color:#fff;opacity:.85;text-align:center;max-width:520px;line-height:1.5}
  #dbcam .title{color:#fff;font:800 22px 'Bricolage Grotesque',Inter,sans-serif}`;
  document.head.appendChild(css);

  let stream = null, facing = 'user';
  function stop() { if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; } }
  function close() { stop(); const o = document.getElementById('dbcam'); if (o) o.remove(); }

  async function start(video, msg) {
    stop();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: facing, width: { ideal: 3840 }, height: { ideal: 2160 } }
      });
      video.srcObject = stream;
      await video.play();
      video.classList.toggle('mirror', facing === 'user');
      msg.textContent = 'Smile! Press the red button. · Senyum! Tekan butang merah.';
    } catch (e) {
      msg.textContent = 'Camera not available. Please allow camera access in the browser (the camera icon in the address bar), then try again. · Kamera tidak dapat dibuka. Benarkan akses kamera dalam pelayar.';
    }
  }

  function open(inp) {
    close();
    const o = document.createElement('div');
    o.id = 'dbcam';
    o.innerHTML = '<div class="title">📸 DarahBot photo booth</div>' +
      '<div class="stage"><video playsinline muted></video><div class="count"></div><div class="flash"></div></div>' +
      '<div class="msg">Opening the camera… · Membuka kamera…</div>' +
      '<div class="bar"><button class="cancel">✕ Cancel · Batal</button><button class="flip">🔄 Switch camera</button>' +
      '<button class="main shoot">📸 Take photo · Ambil gambar</button></div>';
    document.body.appendChild(o);
    const video = o.querySelector('video'), msg = o.querySelector('.msg'), stage = o.querySelector('.stage');
    const count = o.querySelector('.count'), flash = o.querySelector('.flash'), bar = o.querySelector('.bar');
    start(video, msg);
    o.querySelector('.cancel').onclick = close;
    o.querySelector('.flip').onclick = function () { facing = facing === 'user' ? 'environment' : 'user'; start(video, msg); };
    o.querySelector('.shoot').onclick = async function () {
      if (!stream) return;
      bar.style.visibility = 'hidden';
      for (const n of [3, 2, 1]) { count.textContent = n; await new Promise(function (r) { setTimeout(r, 850); }); }
      count.textContent = '';
      flash.classList.remove('go'); void flash.offsetWidth; flash.classList.add('go');
      // full camera resolution, mirrored like the preview (as on a phone's front camera)
      const c = document.createElement('canvas');
      c.width = video.videoWidth; c.height = video.videoHeight;
      const g = c.getContext('2d');
      if (facing === 'user') { g.translate(c.width, 0); g.scale(-1, 1); }
      g.drawImage(video, 0, 0, c.width, c.height);
      stop();
      const url = c.toDataURL('image/jpeg', 0.93);
      video.replaceWith(Object.assign(document.createElement('img'), { src: url }));
      msg.textContent = 'Happy with it? · Puas hati?';
      bar.innerHTML = '<button class="retake">↺ Retake · Ambil semula</button><button class="main use">✓ Use this photo · Guna gambar ini</button>';
      bar.style.visibility = 'visible';
      bar.querySelector('.retake').onclick = function () { open(inp); };
      bar.querySelector('.use').onclick = function () {
        c.toBlob(function (blob) {
          const dt = new DataTransfer();
          dt.items.add(new File([blob], 'darahbot-photo-' + Date.now() + '.jpg', { type: 'image/jpeg' }));
          inp.files = dt.files;
          inp.dispatchEvent(new Event('change', { bubbles: true }));
          close();
        }, 'image/jpeg', 0.93);
      };
    };
  }

  // clicks on a camera box open our camera instead of the file window (the ✕ remove button still works)
  window.addEventListener('click', function (e) {
    const box = e.target.closest && e.target.closest(SEL);
    if (!box || e.target.closest('[data-testid="stFileChipDeleteBtn"]')) return;
    if (!e.target.closest('[data-testid="stFileUploaderDropzone"], [data-testid="stFileUploader"] button, [data-testid="stFileUploader"] section')) return;
    const inp = box.querySelector('input[type=file]');
    if (!inp) return;
    e.preventDefault(); e.stopPropagation();
    open(inp);
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
})();
