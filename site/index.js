// 1. Color scheme toggle (system default -> literal opposite override; revert removes stored override)
(() => {
  const meta = document.querySelector('meta[name="color-scheme"]');
  const toggleBtn = document.getElementById('themeToggle');
  const mediaDark = window.matchMedia('(prefers-color-scheme: dark)');

  function getStored() {
    try {
      const val = localStorage.getItem('color-scheme');
      return val === 'light' || val === 'dark' ? val : null;
    } catch {
      return null;
    }
  }

  function getSystemScheme() {
    return mediaDark.matches ? 'dark' : 'light';
  }

  function applyScheme(stored) {
    meta.content = stored ?? 'light dark';
  }

  toggleBtn.addEventListener('click', () => {
    const currentRendered = getStored() ?? getSystemScheme();
    const target = currentRendered === 'dark' ? 'light' : 'dark';
    const system = getSystemScheme();

    try {
      if (target === system) {
        localStorage.removeItem('color-scheme');
        applyScheme(null);
      } else {
        localStorage.setItem('color-scheme', target);
        applyScheme(target);
      }
    } catch {
      applyScheme(target === system ? null : target);
    }
  });

  window.addEventListener('storage', (event) => {
    if (event.key === 'color-scheme') {
      applyScheme(event.newValue === 'light' || event.newValue === 'dark' ? event.newValue : null);
    }
  });
})();

// 2. Declarative Copy Buttons (Invoker Commands + click fallback + Async Clipboard API)
(() => {
  const timers = new WeakMap();
  let lastMessage = '';

  function legacyCopy(text) {
    const previousFocus = document.activeElement;
    const field = Object.assign(document.createElement('textarea'), { value: text });
    field.setAttribute('readonly', '');
    field.style.cssText = 'position:fixed;inset-block-start:0;opacity:0';
    document.body.append(field);
    field.select();
    try {
      return document.execCommand('copy');
    } finally {
      field.remove();
      previousFocus?.focus({ preventScroll: true });
    }
  }

  function report(button, ok) {
    const tip = button.nextElementSibling;
    clearTimeout(timers.get(button));
    button.removeAttribute('data-copied');
    button.removeAttribute('data-failed');

    let message = ok ? 'Copied' : 'Copy failed';
    if (message === lastMessage) message += '\u00A0';
    lastMessage = message;

    tip.textContent = '';
    void button.offsetWidth;
    button.setAttribute(ok ? 'data-copied' : 'data-failed', '');
    requestAnimationFrame(() => {
      tip.textContent = message;
    });

    timers.set(button, setTimeout(() => {
      button.removeAttribute('data-copied');
      button.removeAttribute('data-failed');
      tip.textContent = '';
    }, 2000));
  }

  async function copyTarget(button, target) {
    const text = target.matches('input, textarea') ? target.value : target.innerText.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      report(button, true);
    } catch {
      try {
        if (!legacyCopy(text)) throw new Error('Copy failed');
        report(button, true);
      } catch {
        report(button, false);
      }
    }
  }

  if ('CommandEvent' in window) {
    document.addEventListener('command', (event) => {
      if (event.command === '--copy' && event.target) {
        copyTarget(event.source, event.target);
      }
    }, true);
  } else {
    document.addEventListener('click', (event) => {
      if (event.defaultPrevented) return;
      const button = event.target.closest('button[command="--copy"]');
      if (!button) return;
      const target = document.getElementById(button.getAttribute('commandfor'));
      if (target) copyTarget(button, target);
    });
  }
})();

// 3. Verified Walkthrough Sandbox (real examples from docs/example-walkthrough.md)
(() => {
  const SCENARIOS = {
    df44: {
      shortcode: 'Df44o7WhunQ',
      rawUrl: 'https://www.instagram.com/p/Df44o7WhunQ/?hl=tr',
      canonicalUrl: 'https://www.instagram.com/reel/Df44o7WhunQ/',
      stage1: { badge: 'EXECUTED', active: true, text: 'Caption length exceeds min_caption_chars (150). Creator: Atalay KARAHAN (@krhnatalay).' },
      stage2: { badge: 'SKIPPED', active: false, text: 'Skipped because Stage 1 caption met the text threshold.' },
      stage3: { badge: 'SKIPPED', active: false, text: 'Skipped because Stage 1 caption met the text threshold.' },
      outputPath: 'sources/reels/Df44o7WhunQ.json (verified extraction output)',
      outputContent: JSON.stringify({
        shortcode: 'Df44o7WhunQ',
        url: 'https://www.instagram.com/p/Df44o7WhunQ/?hl=tr',
        creator: 'Atalay KARAHAN',
        title: 'Video by krhnatalay',
        caption: 'Claude limitin bitiyorsa bu 2 skill\u2019i kur: RTK ve Caveman. 20 dolarl\u0131k abonelik su gibi bitiyorsa ikisini Claude Code\u2019a ekle, token harcamas\u0131n\u0131 azalts\u0131n.\n\nYay\u0131n\u0131n tamam\u0131 YouTube\u2019da: @krhnatalay\n\n#claude #claudecode #yapayzeka #yaz\u0131l\u0131m',
        upload_date: '20261118',
        steps_used: ['metadata'],
        warnings: []
      }, null, 2)
    },
    df2j: {
      shortcode: 'Df2jr_RN9gb',
      rawUrl: 'https://www.instagram.com/p/Df2jr_RN9gb/?hl=tr',
      canonicalUrl: 'https://www.instagram.com/reel/Df2jr_RN9gb/',
      stage1: { badge: 'EXECUTED', active: true, text: 'Caption is 35 chars ("juri yaz sana baglantiyi gondereyim") < 150. Creator: Ahmet Demirci (@ahmetbuilder).' },
      stage2: { badge: 'TRIGGERED', active: true, text: 'Downloads audio to temp dir and transcribes speech via Whisper.' },
      stage3: { badge: 'CONDITIONAL', active: true, text: 'Runs Gemini 2.5 Flash on 4 frames if transcript remains under 40 chars.' },
      outputPath: 'sources/reels/Df2jr_RN9gb.json (Stage 1 verified payload)',
      outputContent: JSON.stringify({
        shortcode: 'Df2jr_RN9gb',
        url: 'https://www.instagram.com/p/Df2jr_RN9gb/?hl=tr',
        creator: 'Ahmet Demirci',
        title: 'Video by ahmetbuilder',
        caption: 'juri yaz sana ba\u011flant\u0131y\u0131 g\u00f6ndereyim',
        upload_date: '20261117',
        steps_used: ['metadata'],
        warnings: []
      }, null, 2)
    },
    ddyn: {
      shortcode: 'DdYn6ekug5W',
      rawUrl: 'https://www.instagram.com/p/DdYn6ekug5W/?hl=tr',
      canonicalUrl: 'https://www.instagram.com/reel/DdYn6ekug5W/',
      stage1: { badge: 'EXECUTED', active: true, text: 'Caption is 85 chars (< 150) and omits repository name. Creator: Bart\u0131n Taha Bak\u0131c\u0131 (@beathabest.tech).' },
      stage2: { badge: 'TRIGGERED', active: true, text: 'Extracts spoken repository name and prompt details via Whisper.' },
      stage3: { badge: 'BYPASSED', active: false, text: 'Skipped once spoken transcript meets min_transcript_chars (40).' },
      outputPath: 'sources/reels/DdYn6ekug5W.json (Stage 1 verified payload)',
      outputContent: JSON.stringify({
        shortcode: 'DdYn6ekug5W',
        url: 'https://www.instagram.com/p/DdYn6ekug5W/?hl=tr',
        creator: 'Bart\u0131n Taha Bak\u0131c\u0131',
        title: 'Video by beathabest.tech',
        caption: 'Bir T\u00fcrk\u2019\u00fcn 170 bin y\u0131ld\u0131zl\u0131 reposu: 2169 haz\u0131r promt! #ai #github #chatgpt #developer',
        upload_date: '20260917',
        steps_used: ['metadata'],
        warnings: []
      }, null, 2)
    },
    dgnt: {
      shortcode: 'DgNTHLDg9X5',
      rawUrl: 'https://www.instagram.com/p/DgNTHLDg9X5/?hl=tr',
      canonicalUrl: 'https://www.instagram.com/reel/DgNTHLDg9X5/',
      stage1: { badge: 'EXECUTED', active: true, text: 'Caption is 438 chars (>= 150). Creator: Copy Paste AI | Tested Prompts (@ai.copypaste).' },
      stage2: { badge: 'BYPASSED', active: false, text: 'Skipped because caption already meets min_caption_chars.' },
      stage3: { badge: 'BYPASSED', active: false, text: 'Skipped; no audio or frame download needed.' },
      outputPath: 'sources/reels/DgNTHLDg9X5.json (verified Groq synthesis)',
      outputContent: JSON.stringify({
        shortcode: 'DgNTHLDg9X5',
        url: 'https://www.instagram.com/p/DgNTHLDg9X5/?hl=tr',
        creator: 'Copy Paste AI | Tested Prompts',
        title: 'Video by ai.copypaste',
        upload_date: '20261126',
        steps_used: ['metadata'],
        warnings: [],
        synthesis_metrics: {
          provider: 'groq',
          model: 'openai/gpt-oss-120b',
          prompt_tokens: 1258,
          completion_tokens: 704,
          total_tokens: 1962,
          retries: 0
        }
      }, null, 2)
    }
  };

  const buttons = document.querySelectorAll('.scenario-btn');

  function selectScenario(key) {
    const s = SCENARIOS[key];
    document.getElementById('simShortcode').textContent = s.shortcode;
    document.getElementById('simRawUrl').textContent = s.rawUrl;
    document.getElementById('simCanonicalUrl').textContent = s.canonicalUrl;

    [1, 2, 3].forEach((n) => {
      const data = s[`stage${n}`];
      const card = document.getElementById(`traceStage${n}`);
      card.dataset.active = String(data.active);
      document.getElementById(`traceStage${n}Badge`).textContent = data.badge;
      document.getElementById(`traceStage${n}Text`).textContent = data.text;
    });

    document.getElementById('simOutputPath').textContent = s.outputPath;
    document.getElementById('simOutputContent').textContent = s.outputContent;

    buttons.forEach((btn) => {
      btn.setAttribute('aria-pressed', String(btn.dataset.scenario === key));
    });
  }

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => selectScenario(btn.dataset.scenario));
  });

  selectScenario('df44');
})();

// 4. Accessible Tabbed Interface (roving tabindex, arrow keys, hidden="until-found", beforematch)
(() => {
  const tablist = document.querySelector('[role="tablist"]');
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));

  function activateTab(tab, moveFocus = false) {
    const index = tabs.indexOf(tab);
    tabs.forEach((t, i) => {
      const selected = i === index;
      t.setAttribute('aria-selected', String(selected));
      t.tabIndex = selected ? 0 : -1;
      const panel = panels[i];
      if (selected) {
        panel.removeAttribute('hidden');
        panel.tabIndex = 0;
      } else {
        panel.setAttribute('hidden', 'until-found');
        panel.removeAttribute('tabindex');
      }
    });
    tab.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (moveFocus) tab.focus();
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => activateTab(tab, false));
  });

  tablist.addEventListener('keydown', (event) => {
    const current = tabs.indexOf(document.activeElement);
    if (current === -1) return;

    let next = null;
    if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;

    if (next !== null) {
      event.preventDefault();
      activateTab(tabs[next], true);
    }
  });

  panels.forEach((panel, idx) => {
    panel.addEventListener('beforematch', () => activateTab(tabs[idx], false));
  });
})();
