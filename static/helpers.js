const TEAM_COLORS = {
  // 2026 teams
  'red_bull':'#3671C6','ferrari':'#E8002D','mercedes':'#27F4D2','mclaren':'#FF8000',
  'aston_martin':'#229971','alpine':'#FF87BC','williams':'#64C4FF',
  'racing_bulls':'#6692FF','rb':'#6692FF',
  'kick_sauber':'#F50537','audi':'#F50537','sauber':'#F50537',
  'haas':'#B6BABD','cadillac':'#4B4BFF',
  // Historic teams
  'alfa':'#B12335','alphatauri':'#5E8FAA','toro_rosso':'#469BFF',
  'renault':'#FFF500','racing_point':'#F596C8','force_india':'#F596C8',
  'manor':'#AE1D25','lotus_f1':'#FFB800','caterham':'#00A550',
  'marussia':'#6E0000','hrt':'#CC8A00','virgin':'#CC0000',
  'default':'#E10600'
};

function teamColor(id) {
  if (!id) return TEAM_COLORS.default;
  const clean = id.toLowerCase().replace(/[-\s]/g,'_');
  return TEAM_COLORS[clean] || TEAM_COLORS[id] || TEAM_COLORS.default;
}

function flagEmoji(nat) {
  const f = {
    'British':'🇬🇧','German':'🇩🇪','Dutch':'🇳🇱','Spanish':'🇪🇸','French':'🇫🇷',
    'Australian':'🇦🇺','Canadian':'🇨🇦','Finnish':'🇫🇮','Mexican':'🇲🇽','Monegasque':'🇲🇨',
    'Italian':'🇮🇹','Japanese':'🇯🇵','Thai':'🇹🇭','Danish':'🇩🇰','Chinese':'🇨🇳',
    'American':'🇺🇸','Brazilian':'🇧🇷','Argentine':'🇦🇷','Belgian':'🇧🇪','Austrian':'🇦🇹',
    'New Zealander':'🇳🇿','Swiss':'🇨🇭','Russian':'🇷🇺','Polish':'🇵🇱','Venezuelan':'🇻🇪',
    'Colombian':'🇨🇴','Swedish':'🇸🇪','Indonesian':'🇮🇩'
  };
  return f[nat] || '🏁';
}

function timeAgo(dateStr) {
  const diff = Math.floor((new Date() - new Date(dateStr)) / 1000);
  if (diff < 60) return `${diff}s geleden`;
  if (diff < 3600) return `${Math.floor(diff/60)}m geleden`;
  if (diff < 86400) return `${Math.floor(diff/3600)}u geleden`;
  return `${Math.floor(diff/86400)}d geleden`;
}

function daysUntil(dateStr) {
  return Math.ceil((new Date(dateStr) - new Date()) / (1000*60*60*24));
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('nl-NL',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
}

async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`API fout ${res.status}: ${url}`);
      return null;
    }
    const data = await res.json();
    return data;
  } catch(e) {
    console.error('API fout:', url, e.message);
    return null;
  }
}

// Show error in element
function showError(elId, msg) {
  const el = document.getElementById(elId);
  if (el) el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-text">${msg}</div></div>`;
}
