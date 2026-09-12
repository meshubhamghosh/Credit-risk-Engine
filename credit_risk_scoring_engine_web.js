const MODEL = {
  features: ["bureau_score","credit_utilization","debt_to_income","years_employed","credit_history_yrs","num_credit_inquiries_6m"],
  weights: [-0.00556820403923916, 2.746505104171754, 1.4037234644183443, -0.051693867519108386, -0.0025797661582479267, 0.030691186608634076],
  intercept: 1.9370330360893218
};

const inputs = {};
MODEL.features.forEach(f => { inputs[f] = document.getElementById(f); });

const themeToggle = document.getElementById('theme-toggle');
const themeLabel = document.getElementById('theme-label');
const themeIcon = themeToggle.querySelector('.theme-icon');

function setTheme(isDark) {
  document.body.classList.toggle('dark-mode', isDark);
  themeToggle.setAttribute('aria-pressed', String(isDark));
  themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  themeLabel.textContent = isDark ? 'Light mode' : 'Dark mode';
  themeIcon.innerHTML = isDark ? '&#9728;' : '&#9790;';
  localStorage.setItem('credit-risk-theme', isDark ? 'dark' : 'light');
}

setTheme(localStorage.getItem('credit-risk-theme') === 'dark');
themeToggle.addEventListener('click', () => {
  setTheme(!document.body.classList.contains('dark-mode'));
});

const displayTransform = {
  bureau_score: v => v,
  credit_utilization: v => v / 100,
  debt_to_income: v => v / 100,
  years_employed: v => v,
  credit_history_yrs: v => v,
  num_credit_inquiries_6m: v => v
};

const featureLabels = {
  bureau_score: "Bureau score",
  credit_utilization: "Utilization",
  debt_to_income: "Debt-to-income",
  years_employed: "Years employed",
  credit_history_yrs: "Credit history",
  num_credit_inquiries_6m: "Inquiries (6m)"
};

function computeScore() {
  let logit = MODEL.intercept;
  const contributions = [];

  MODEL.features.forEach((f, i) => {
    const rawVal = parseFloat(inputs[f].value);
    const modelVal = displayTransform[f](rawVal);
    const contribution = MODEL.weights[i] * modelVal;
    logit += contribution;
    contributions.push({ name: f, contribution });

    document.getElementById('val-' + f).textContent =
      (f === 'credit_utilization' || f === 'debt_to_income') ? rawVal : rawVal;
  });

  const prob = 1 / (1 + Math.exp(-logit));
  const score = Math.round(300 + (1 - prob) * 600);

  let band, bandClass;
  if (score >= 750) { band = "LOW RISK"; bandClass = "band-low"; }
  else if (score >= 650) { band = "MEDIUM RISK"; bandClass = "band-medium"; }
  else if (score >= 550) { band = "HIGH RISK"; bandClass = "band-high"; }
  else { band = "VERY HIGH RISK"; bandClass = "band-vhigh"; }

  document.getElementById('score-number').textContent = score;
  document.getElementById('stat-prob').textContent = (prob * 100).toFixed(1) + '%';
  document.getElementById('stat-logit').textContent = logit.toFixed(2);

  const pill = document.getElementById('band-pill');
  pill.textContent = band;
  pill.className = 'band-pill ' + bandClass;

  renderContributions(contributions);
}

function renderContributions(contributions) {
  const maxAbs = Math.max(...contributions.map(c => Math.abs(c.contribution)), 0.01);
  const container = document.getElementById('contrib-container');
  container.innerHTML = '';

  contributions.forEach(c => {
    const pct = Math.min(Math.abs(c.contribution) / maxAbs * 50, 50);
    const row = document.createElement('div');
    row.className = 'contrib-row';

    const name = document.createElement('div');
    name.className = 'contrib-name';
    name.textContent = featureLabels[c.name];

    const track = document.createElement('div');
    track.className = 'contrib-track';

    const centerLine = document.createElement('div');
    centerLine.className = 'contrib-center-line';
    track.appendChild(centerLine);

    const fill = document.createElement('div');
    fill.className = 'contrib-fill ' + (c.contribution >= 0 ? 'pos' : 'neg');
    fill.style.width = pct + '%';
    track.appendChild(fill);

    const val = document.createElement('div');
    val.className = 'contrib-val';
    val.textContent = c.contribution.toFixed(2);

    row.appendChild(name);
    row.appendChild(track);
    row.appendChild(val);
    container.appendChild(row);
  });
}

const presets = {
  low: { bureau_score: 800, credit_utilization: 10, debt_to_income: 15, years_employed: 12, credit_history_yrs: 15, num_credit_inquiries_6m: 0 },
  typical: { bureau_score: 700, credit_utilization: 30, debt_to_income: 40, years_employed: 5, credit_history_yrs: 6, num_credit_inquiries_6m: 1 },
  high: { bureau_score: 560, credit_utilization: 85, debt_to_income: 95, years_employed: 1, credit_history_yrs: 1, num_credit_inquiries_6m: 5 }
};

document.querySelectorAll('.presets button').forEach(btn => {
  btn.addEventListener('click', () => {
    const preset = presets[btn.dataset.preset];
    Object.keys(preset).forEach(f => { inputs[f].value = preset[f]; });
    computeScore();
  });
});

MODEL.features.forEach(f => {
  inputs[f].addEventListener('input', computeScore);
});

computeScore();
