// Cyberpunk SVG scene generators

// Holographic core: layered concentric tech rings with data nodes
window.SceneHoloCore = function(opts = {}) {
  const s = opts.size || 600;
  return `
<svg viewBox="0 0 600 600" width="${s}" height="${s}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="hcore" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#7dd3fc" stop-opacity="0.9"/>
      <stop offset="40%" stop-color="#bb9af7" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#7dd3fc" stop-opacity="0"/>
    </radialGradient>
    <filter id="hglow"><feGaussianBlur stdDeviation="3"/></filter>
    <linearGradient id="hscan" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#7dd3fc" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#7dd3fc" stop-opacity="0.6"/>
      <stop offset="1" stop-color="#7dd3fc" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <!-- core glow -->
  <circle cx="300" cy="300" r="280" fill="url(#hcore)"/>
  <!-- outer ring with data ticks -->
  <g fill="none" stroke="#7dd3fc" stroke-width="1" opacity="0.7">
    <circle cx="300" cy="300" r="260">
      <animateTransform attributeName="transform" type="rotate" from="0 300 300" to="360 300 300" dur="180s" repeatCount="indefinite"/>
    </circle>
    <circle cx="300" cy="300" r="220" stroke-dasharray="2 6">
      <animateTransform attributeName="transform" type="rotate" from="360 300 300" to="0 300 300" dur="100s" repeatCount="indefinite"/>
    </circle>
    <circle cx="300" cy="300" r="180" stroke="#bb9af7"/>
    <circle cx="300" cy="300" r="140" stroke-dasharray="1 12" stroke="#2dd4bf">
      <animateTransform attributeName="transform" type="rotate" from="0 300 300" to="-360 300 300" dur="60s" repeatCount="indefinite"/>
    </circle>
    <circle cx="300" cy="300" r="100"/>
    <circle cx="300" cy="300" r="60" stroke="#bb9af7"/>
  </g>
  <!-- crosshair -->
  <g stroke="#565f89" stroke-width="0.5" opacity="0.6">
    <line x1="300" y1="20" x2="300" y2="580"/>
    <line x1="20" y1="300" x2="580" y2="300"/>
  </g>
  <!-- corner ticks on outer ring -->
  <g stroke="#7dd3fc" stroke-width="2" opacity="0.9">
    <line x1="300" y1="20" x2="300" y2="40"/>
    <line x1="300" y1="560" x2="300" y2="580"/>
    <line x1="20" y1="300" x2="40" y2="300"/>
    <line x1="560" y1="300" x2="580" y2="300"/>
  </g>
  <!-- orbiting data nodes -->
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 300 300" to="360 300 300" dur="40s" repeatCount="indefinite"/>
    <circle cx="300" cy="40" r="5" fill="#7dd3fc" filter="url(#hglow)"/>
    <rect x="296" y="36" width="8" height="8" fill="none" stroke="#7dd3fc"/>
    <text x="320" y="46" fill="#7dd3fc" font-family="JetBrains Mono" font-size="11" opacity="0.8">0xA1F2</text>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="120 300 300" to="480 300 300" dur="50s" repeatCount="indefinite"/>
    <circle cx="300" cy="80" r="5" fill="#bb9af7" filter="url(#hglow)"/>
    <text x="320" y="86" fill="#bb9af7" font-family="JetBrains Mono" font-size="11" opacity="0.8">π_θ</text>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="240 300 300" to="600 300 300" dur="60s" repeatCount="indefinite"/>
    <circle cx="300" cy="120" r="4" fill="#2dd4bf" filter="url(#hglow)"/>
    <text x="320" y="124" fill="#2dd4bf" font-family="JetBrains Mono" font-size="11" opacity="0.8">KL</text>
  </g>
  <!-- scanline sweep -->
  <rect x="40" y="298" width="520" height="4" fill="url(#hscan)" opacity="0.8">
    <animate attributeName="y" values="40;560;40" dur="6s" repeatCount="indefinite"/>
  </rect>
  <!-- center reactor -->
  <circle cx="300" cy="300" r="20" fill="#c0caf5" filter="url(#hglow)" opacity="0.95">
    <animate attributeName="r" values="16;24;16" dur="2.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="300" cy="300" r="6" fill="#fff"/>
  <!-- data text in corners -->
  <g fill="#565f89" font-family="JetBrains Mono" font-size="10" opacity="0.7">
    <text x="30" y="30">SYS::POLICY-CORE</text>
    <text x="450" y="30" text-anchor="end" x-orig="450">ONLINE</text>
    <text x="30" y="585">v.4.7.1</text>
    <text x="570" y="585" text-anchor="end">UTC+0</text>
  </g>
</svg>`;
};

// Circuit board — nodes connected by orthogonal traces
window.SceneCircuit = function(opts = {}) {
  const w = opts.w || 600, h = opts.h || 600;
  return `
<svg viewBox="0 0 600 600" width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="cglow"><feGaussianBlur stdDeviation="2"/></filter>
  </defs>
  <g stroke="#7dd3fc" stroke-width="1" fill="none" opacity="0.45">
    <path d="M 50 100 L 200 100 L 200 50 L 350 50 L 350 150"/>
    <path d="M 50 200 L 150 200 L 150 280 L 320 280 L 320 200 L 500 200"/>
    <path d="M 100 350 L 280 350 L 280 420 L 450 420"/>
    <path d="M 50 480 L 200 480 L 200 540 L 400 540"/>
    <path d="M 500 100 L 500 250 L 420 250 L 420 380"/>
    <path d="M 550 350 L 550 480"/>
  </g>
  <g stroke="#bb9af7" stroke-width="0.8" fill="none" opacity="0.4">
    <path d="M 80 80 L 80 250 L 230 250"/>
    <path d="M 380 80 L 380 200"/>
    <path d="M 250 480 L 250 380 L 380 380"/>
  </g>
  <g fill="#7dd3fc">
    <circle cx="50" cy="100" r="3" filter="url(#cglow)"/>
    <circle cx="200" cy="50" r="3"/>
    <circle cx="350" cy="150" r="4" fill="#bb9af7" filter="url(#cglow)"/>
    <circle cx="320" cy="200" r="3"/>
    <circle cx="500" cy="200" r="4" fill="#2dd4bf" filter="url(#cglow)"/>
    <circle cx="280" cy="420" r="4" filter="url(#cglow)"/>
    <circle cx="450" cy="420" r="3" fill="#bb9af7"/>
    <circle cx="200" cy="540" r="3"/>
    <circle cx="420" cy="380" r="4" fill="#bb9af7" filter="url(#cglow)"/>
    <circle cx="550" cy="350" r="3"/>
    <circle cx="80" cy="80" r="2"/>
    <circle cx="380" cy="80" r="3" fill="#2dd4bf"/>
  </g>
  <g fill="none" stroke="#bb9af7" stroke-width="1" opacity="0.7">
    <rect x="190" y="270" width="60" height="40" rx="2"/>
    <rect x="380" y="370" width="80" height="50" rx="2"/>
  </g>
  <g font-family="JetBrains Mono" font-size="9" fill="#565f89" opacity="0.7">
    <text x="195" y="288">CORE-01</text>
    <text x="385" y="390">REWARD</text>
    <text x="385" y="405">MODULE</text>
  </g>
  <!-- pulses along traces -->
  <circle r="3" fill="#fff" opacity="0.9">
    <animateMotion dur="4s" repeatCount="indefinite" path="M 50 100 L 200 100 L 200 50 L 350 50 L 350 150"/>
  </circle>
  <circle r="3" fill="#bb9af7" opacity="0.9">
    <animateMotion dur="6s" repeatCount="indefinite" path="M 50 200 L 150 200 L 150 280 L 320 280 L 320 200 L 500 200"/>
  </circle>
  <circle r="2.5" fill="#2dd4bf" opacity="0.9">
    <animateMotion dur="5s" repeatCount="indefinite" path="M 100 350 L 280 350 L 280 420 L 450 420"/>
  </circle>
</svg>`;
};

// Wireframe city skyline
window.SceneCity = function() {
  return `
<svg viewBox="0 0 1920 600" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
  <defs>
    <linearGradient id="cityfog" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#0b0d1a" stop-opacity="0"/>
      <stop offset="80%" stop-color="#0b0d1a"/>
    </linearGradient>
    <linearGradient id="bld" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#1a1b3a"/>
      <stop offset="1" stop-color="#0b0d1a"/>
    </linearGradient>
  </defs>
  <!-- back layer -->
  <g fill="url(#bld)" stroke="#7dd3fc" stroke-width="0.5" opacity="0.5">
    <rect x="60" y="280" width="80" height="320"/>
    <rect x="180" y="240" width="60" height="360"/>
    <rect x="280" y="200" width="100" height="400"/>
    <rect x="420" y="260" width="70" height="340"/>
    <rect x="530" y="180" width="90" height="420"/>
    <rect x="660" y="220" width="80" height="380"/>
    <rect x="780" y="160" width="120" height="440"/>
    <rect x="940" y="240" width="70" height="360"/>
    <rect x="1050" y="190" width="100" height="410"/>
    <rect x="1190" y="220" width="80" height="380"/>
    <rect x="1310" y="170" width="110" height="430"/>
    <rect x="1460" y="250" width="80" height="350"/>
    <rect x="1580" y="200" width="100" height="400"/>
    <rect x="1720" y="240" width="80" height="360"/>
    <rect x="1830" y="220" width="80" height="380"/>
  </g>
  <!-- window grid -->
  <g fill="#7dd3fc" opacity="0.6">
    ${(() => {
      const buildings = [[60,280,80,320],[180,240,60,360],[280,200,100,400],[420,260,70,340],[530,180,90,420],[660,220,80,380],[780,160,120,440],[940,240,70,360],[1050,190,100,410],[1190,220,80,380],[1310,170,110,430],[1460,250,80,350],[1580,200,100,400],[1720,240,80,360],[1830,220,80,380]];
      let out = '';
      for (const [x,y,w,h] of buildings) {
        for (let row = 0; row < Math.floor(h/30) - 1; row++) {
          for (let col = 0; col < Math.floor(w/14); col++) {
            if (Math.random() < 0.3) {
              const c = Math.random() < 0.15 ? '#bb9af7' : (Math.random() < 0.1 ? '#e0af68' : '#7dd3fc');
              out += `<rect x="${x + 4 + col*14}" y="${y + 12 + row*30}" width="6" height="10" fill="${c}" opacity="${0.3 + Math.random()*0.5}"/>`;
            }
          }
        }
      }
      return out;
    })()}
  </g>
  <!-- antennas with blinking lights -->
  <g stroke="#7dd3fc" stroke-width="1">
    <line x1="320" y1="200" x2="320" y2="160"/>
    <line x1="580" y1="180" x2="580" y2="130"/>
    <line x1="840" y1="160" x2="840" y2="100"/>
    <line x1="1100" y1="190" x2="1100" y2="140"/>
    <line x1="1360" y1="170" x2="1360" y2="120"/>
    <line x1="1630" y1="200" x2="1630" y2="155"/>
  </g>
  <g fill="#f7768e">
    <circle cx="320" cy="160" r="2"><animate attributeName="opacity" values="1;0.2;1" dur="2s" repeatCount="indefinite"/></circle>
    <circle cx="580" cy="130" r="2"><animate attributeName="opacity" values="1;0.2;1" dur="2.4s" repeatCount="indefinite"/></circle>
    <circle cx="840" cy="100" r="2.5"><animate attributeName="opacity" values="1;0.2;1" dur="1.8s" repeatCount="indefinite"/></circle>
    <circle cx="1100" cy="140" r="2"><animate attributeName="opacity" values="1;0.2;1" dur="2.2s" repeatCount="indefinite"/></circle>
    <circle cx="1360" cy="120" r="2"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>
    <circle cx="1630" cy="155" r="2"><animate attributeName="opacity" values="1;0.2;1" dur="2.6s" repeatCount="indefinite"/></circle>
  </g>
  <rect x="0" y="0" width="1920" height="600" fill="url(#cityfog)"/>
</svg>`;
};

// Token flow diagram (kept from before)
window.SceneTokenFlow = function() {
  return `
<svg viewBox="0 0 800 200" xmlns="http://www.w3.org/2000/svg" width="100%">
  <defs>
    <linearGradient id="tflow" x1="0" x2="1">
      <stop offset="0" stop-color="#7dd3fc" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#7dd3fc"/>
      <stop offset="1" stop-color="#bb9af7" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <g font-family="JetBrains Mono, monospace" font-size="14" fill="#a9b1d6">
    ${Array.from({length: 12}).map((_, i) => {
      const x = 40 + i * 62;
      return `
      <rect x="${x}" y="80" width="50" height="40" fill="rgba(125,211,252,0.06)" stroke="#3b4261"/>
      <text x="${x+25}" y="105" text-anchor="middle" fill="#7dd3fc">t${i+1}</text>
      <circle cx="${x+25}" cy="60" r="3" fill="#bb9af7" opacity="${0.3 + Math.sin(i)*0.3 + 0.4}">
        <animate attributeName="cy" values="60;50;60" dur="${2+i*0.2}s" repeatCount="indefinite"/>
      </circle>
      `;
    }).join('')}
    <line x1="40" y1="100" x2="780" y2="100" stroke="url(#tflow)" stroke-width="1" opacity="0.4"/>
  </g>
</svg>`;
};

window.SceneKLDist = function() {
  return `
<svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg" width="100%">
  <defs>
    <linearGradient id="dref" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#7dd3fc" stop-opacity="0.4"/>
      <stop offset="1" stop-color="#7dd3fc" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="dpol" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#bb9af7" stop-opacity="0.4"/>
      <stop offset="1" stop-color="#bb9af7" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <line x1="20" y1="260" x2="580" y2="260" stroke="#3b4261"/>
  <path d="M 20 260 Q 200 60, 320 260 Q 320 60, 580 260 Z" fill="url(#dref)" stroke="#7dd3fc" stroke-width="1.5" opacity="0.85" transform="scale(0.7,1) translate(40,0)"/>
  <path d="M 20 260 Q 200 60, 320 260 Q 320 60, 580 260 Z" fill="url(#dpol)" stroke="#bb9af7" stroke-width="1.5" opacity="0.85" transform="scale(0.7,1) translate(180,0)">
    <animateTransform attributeName="transform" type="translate" values="180 0;200 0;180 0" dur="6s" repeatCount="indefinite" additive="sum"/>
  </path>
  <text x="120" y="290" fill="#7dd3fc" font-family="JetBrains Mono" font-size="16">π_ref</text>
  <text x="450" y="290" fill="#bb9af7" font-family="JetBrains Mono" font-size="16">π_θ</text>
  <text x="300" y="40" text-anchor="middle" fill="#565f89" font-family="JetBrains Mono" font-size="14" letter-spacing="2">KL DIVERGENCE</text>
</svg>`;
};
