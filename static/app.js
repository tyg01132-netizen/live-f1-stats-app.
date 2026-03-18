// ── Team colours ─────────────────────────────────────────────────────────────
const TEAM_COLOURS = {
  red_bull:'#3671C6',mercedes:'#27F4D2',ferrari:'#E8002D',mclaren:'#FF8000',
  alpine:'#FF87BC',aston_martin:'#229971',williams:'#64C4FF',haas:'#B6BABD',
  sauber:'#52E252',kick_sauber:'#52E252',audi:'#F50537',rb:'#6692FF',
  racing_bulls:'#6692FF',alphatauri:'#5E8FAA',alpha_tauri:'#5E8FAA',
  renault:'#FFF500',force_india:'#FF80C7',racing_point:'#F596C8',
  cadillac:'#4B4BFF',toro_rosso:'#4694D0',
};
function teamColor(id) {
  if (!id) return '#666';
  const k = (id+'').toLowerCase().replace(/-/g,'_');
  for (const [key, val] of Object.entries(TEAM_COLOURS))
    if (k.includes(key) || key.includes(k)) return val;
  let h=0; for(let i=0;i<k.length;i++) h=(h*31+k.charCodeAt(i))&0xffffffff;
  return `hsl(${Math.abs(h)%360},60%,50%)`;
}

// ── Flags ─────────────────────────────────────────────────────────────────────
const FLAGS = {
  Australian:'🇦🇺',British:'🇬🇧',German:'🇩🇪',Spanish:'🇪🇸',Finnish:'🇫🇮',
  Dutch:'🇳🇱',Mexican:'🇲🇽',Monegasque:'🇲🇨',Canadian:'🇨🇦',French:'🇫🇷',
  Japanese:'🇯🇵',Danish:'🇩🇰',Thai:'🇹🇭',Chinese:'🇨🇳',American:'🇺🇸',
  Italian:'🇮🇹',Brazilian:'🇧🇷',Austrian:'🇦🇹','New Zealander':'🇳🇿',
  'South African':'🇿🇦',Swiss:'🇨🇭',Polish:'🇵🇱',Argentine:'🇦🇷',Belgian:'🇧🇪',
  Hungarian:'🇭🇺',Swedish:'🇸🇪',Colombian:'🇨🇴',Portuguese:'🇵🇹',Czech:'🇨🇿',
  Australian:'🇦🇺',Bahrain:'🇧🇭','Saudi Arabia':'🇸🇦',China:'🇨🇳',USA:'🇺🇸',
  Italy:'🇮🇹',Monaco:'🇲🇨',Canada:'🇨🇦',Spain:'🇪🇸',Austria:'🇦🇹',
  'Great Britain':'🇬🇧',UK:'🇬🇧',Hungary:'🇭🇺',Belgium:'🇧🇪',Netherlands:'🇳🇱',
  Azerbaijan:'🇦🇿',Singapore:'🇸🇬',Japan:'🇯🇵',Qatar:'🇶🇦',Mexico:'🇲🇽',
  Brazil:'🇧🇷','Abu Dhabi':'🇦🇪','United Arab Emirates':'🇦🇪',
};
function flag(name) { return FLAGS[name] || '🏁'; }

// ── Dates ─────────────────────────────────────────────────────────────────────
const MO = ['Jan','Feb','Mrt','Apr','Mei','Jun','Jul','Aug','Sep','Okt','Nov','Dec'];
const MO_FULL = ['Januari','Februari','Maart','April','Mei','Juni','Juli','Augustus','September','Oktober','November','December'];
function fmtDate(s) {
  if(!s) return '';
  const d = new Date(s+'T12:00:00');
  return `${d.getDate()} ${MO[d.getMonth()]} ${d.getFullYear()}`;
}
function fmtShort(s) {
  if(!s) return '';
  const d = new Date(s+'T12:00:00');
  return `${d.getDate()} ${MO[d.getMonth()]}`;
}
function daysUntil(s) { return Math.ceil((new Date(s+'T12:00:00')-Date.now())/86400000); }
function monthOf(s)    { return new Date(s+'T12:00:00').getMonth(); }

// ── API fetch ─────────────────────────────────────────────────────────────────
async function get(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) { console.error(`[API] ${url} → ${r.status}`); _showErr(url,`HTTP ${r.status}`); return null; }
    return await r.json();
  } catch(e) { console.error(`[API] ${url}:`,e); _showErr(url,e.message); return null; }
}
function _showErr(url, msg) {
  let bar = document.getElementById('_errs');
  if(!bar) {
    bar = document.createElement('div');
    bar.id='_errs';
    bar.style.cssText='position:fixed;bottom:1rem;right:1rem;z-index:9999;max-width:360px;display:flex;flex-direction:column;gap:4px;pointer-events:none';
    document.body.appendChild(bar);
  }
  const d = document.createElement('div');
  d.style.cssText='background:#160000;border:1px solid #e1060044;border-radius:6px;padding:6px 10px;font:600 11px/1.4 monospace;color:#ff6060';
  d.textContent=`❌ ${url.replace('/api/','')} — ${msg}`;
  bar.appendChild(d);
  setTimeout(()=>d.remove(),7000);
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
function el(id)      { return document.getElementById(id); }
function qs(s)       { return document.querySelector(s); }
function html(id, h) { const e=el(id); if(e) e.innerHTML=h; }
function empty(id, icon, msg) { html(id,`<div class="empty"><div class="icon">${icon}</div><span>${msg}</span></div>`); }
function loading(id) { html(id,'<div class="loading"><div class="spinner"></div><span>Laden...</span></div>'); }

// ── FIXED Tabs — panes can be siblings or anywhere in document ────────────────
function initTabs(wrapId) {
  const wrap = document.getElementById(wrapId) || document.querySelector(wrapId);
  if (!wrap) return;
  wrap.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // Look for panes in the PARENT of wrap, not inside wrap
      const parent = wrap.closest('.tab-root') || wrap.parentElement;
      parent.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      const pane = document.getElementById(btn.dataset.tab) ||
                   parent.querySelector('#' + btn.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });
}

// ── Inline tab toggle (for dynamically injected HTML) ────────────────────────
function initTabsIn(rootEl) {
  if (!rootEl) return;
  rootEl.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const root = btn.closest('.tab-root');
      if (!root) return;
      root.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      root.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = root.querySelector('#' + btn.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });
}

// ── Live pill ─────────────────────────────────────────────────────────────────
async function checkLive() {
  try {
    const d = await get('/api/live/status');
    if (d?.active) document.querySelectorAll('.live-pill').forEach(p=>p.classList.add('is-live'));
  } catch(e) {}
}
checkLive();

// ── Flag images (flagcdn.com) ─────────────────────────────────────────────────
const FLAG_ISO = {
  // Countries
  Australia:'au', Bahrain:'bh', 'Saudi Arabia':'sa', China:'cn', Japan:'jp',
  USA:'us', 'United States':'us', Italy:'it', Monaco:'mc', Canada:'ca',
  Spain:'es', Austria:'at', 'Great Britain':'gb', UK:'gb', Hungary:'hu',
  Belgium:'be', Netherlands:'nl', Azerbaijan:'az', Singapore:'sg',
  Qatar:'qa', Mexico:'mx', Brazil:'br', 'Abu Dhabi':'ae', 'United Arab Emirates':'ae',
  // Nationalities
  Australian:'au', British:'gb', German:'de', Spanish:'es', Finnish:'fi',
  Dutch:'nl', Mexican:'mx', Monegasque:'mc', Canadian:'ca', French:'fr',
  Japanese:'jp', Danish:'dk', Thai:'th', Chinese:'cn', American:'us',
  'New Zealander':'nz', 'South African':'za', Swiss:'ch', Polish:'pl',
  Argentine:'ar', Belgian:'be', Hungarian:'hu', Swedish:'se', Colombian:'co',
  Portuguese:'pt', Czech:'cz', Austrian:'at', Brazilian:'br', Italian:'it',
  Russian:'ru', Venezuelan:'ve', Scottish:'gb',
};
function flagImg(name, size=20) {
  const iso = FLAG_ISO[name];
  if (!iso) return `<span style="font-size:${size}px">${flag(name)}</span>`;
  return `<img src="https://flagcdn.com/w40/${iso}.png" alt="${name}" style="width:${size*1.4}px;height:${size}px;object-fit:cover;border-radius:2px;vertical-align:middle">`;
}

// ── Circuit photos via Wikipedia ──────────────────────────────────────────────
const _photoCache = {};
async function getCircuitPhoto(circuitId) {
  if (_photoCache[circuitId] !== undefined) return _photoCache[circuitId];
  try {
    const r = await fetch(`/api/photo/${circuitId}`);
    const d = await r.json();
    _photoCache[circuitId] = d.url || '';
    return _photoCache[circuitId];
  } catch(e) { _photoCache[circuitId] = ''; return ''; }
}

// ── Nav logo HTML ─────────────────────────────────────────────────────────────
const NAV_LOGO = `<a class="nav-logo" href="/" style="display:flex;align-items:center;gap:8px;text-decoration:none">
  <svg width="26" height="26" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="13" fill="#e10600"/>
  <path d="M7 14h14M14 7v14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="14" cy="14" r="3" fill="white"/></svg>
  <span style="font-family:var(--font-display);font-size:1.25rem;font-weight:900;letter-spacing:-0.5px;color:var(--txt)">F1<span style="color:#e10600">FOR</span>LIVE</span>
</a>`;

// ── PUSH NOTIFICATIONS ────────────────────────────────────────────────────────
window.F1Notif = {
  async requestPermission() {
    if (!('Notification' in window)) return false;
    if (Notification.permission === 'granted') return true;
    if (Notification.permission === 'denied') return false;
    const result = await Notification.requestPermission();
    return result === 'granted';
  },

  schedule(title, body, delayMs) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (delayMs <= 0) return;
    setTimeout(() => {
      new Notification(title, {
        body, icon: '/static/f1-icon.png',
        badge: '/static/f1-icon.png',
        tag: title,
      });
    }, delayMs);
  },

  async scheduleRaceWeekend(sessions) {
    if (!await this.requestPermission()) return;
    const now = Date.now();
    const HOUR = 3600000;
    Object.entries(sessions).forEach(([key, s]) => {
      if (!s?.iso) return;
      const t = new Date(s.iso).getTime();
      const labels = { FirstPractice:'VT1', SecondPractice:'VT2', ThirdPractice:'VT3',
                       Qualifying:'Kwalificatie', Sprint:'Sprint Race', SprintQualifying:'Sprint Kwalificatie' };
      const lbl = labels[key] || key;
      // 1hr before
      const delay1 = t - HOUR - now;
      if (delay1 > 0) this.schedule(`🏎 ${lbl} over 1 uur`, `F1FORLIFE — ${lbl} begint om ${new Date(t).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})}`, delay1);
    });
  },

  showPrompt(sessions) {
    if (!('Notification' in window) || Notification.permission !== 'default') return;
    if (localStorage.getItem('notif_dismissed')) return;
    const p = document.createElement('div');
    p.className = 'notif-prompt';
    p.innerHTML = `
      <div class="np-text">
        <div class="np-title">🔔 Race-herinneringen</div>
        <div class="np-sub">Ontvang een melding 1 uur voor elke sessie</div>
      </div>
      <button class="np-btn np-yes" id="np-yes">Aanzetten</button>
      <button class="np-btn np-no"  id="np-no">Later</button>
    `;
    document.body.appendChild(p);
    document.getElementById('np-yes').onclick = async () => {
      await this.scheduleRaceWeekend(sessions);
      p.remove();
    };
    document.getElementById('np-no').onclick = () => {
      localStorage.setItem('notif_dismissed', '1');
      p.remove();
    };
    setTimeout(() => p.remove(), 12000);
  }
};

// ── Scroll-triggered animations ───────────────────────────────────────────────
(function() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('anim-visible');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12 });

  function observe() {
    document.querySelectorAll('.anim, .anim-stagger').forEach(el => io.observe(el));
  }

  // Run on load and whenever new content might be injected
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', observe);
  } else {
    observe();
  }
  // Re-observe after dynamic content loads (called from data loaders)
  window._reobserve = observe;
})();

// ── Animated number counter ───────────────────────────────────────────────────
function animateNumber(el, target, duration = 800, suffix = '') {
  if (!el) return;
  const start = 0;
  const startTime = performance.now();
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease out cubic
    const current = Math.round(start + (target - start) * eased);
    el.textContent = current + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
window.animateNumber = animateNumber;

// ── Dark / Light mode toggle ──────────────────────────────────────────────────
(function() {
  // Detect system preference
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const saved = localStorage.getItem('f1_theme');

  function applyTheme(theme) {
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    localStorage.setItem('f1_theme', theme);
    // Update all knobs
    document.querySelectorAll('.theme-btn-knob').forEach(k => {
      k.textContent = theme === 'light' ? '☀' : '🌙';
    });
  }

  // Init on load
  const initTheme = saved || (prefersDark.matches ? 'dark' : 'light');
  applyTheme(initTheme);

  // Listen for system changes (only if no manual override)
  prefersDark.addEventListener('change', e => {
    if (!localStorage.getItem('f1_theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  // Toggle handler - works for any .theme-btn on the page
  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  };
})();
