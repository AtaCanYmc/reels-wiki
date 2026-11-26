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
    },
    ytvp: {
      shortcode: 'yt_VpW4T7e34EI',
      rawUrl: 'https://www.youtube.com/shorts/VpW4T7e34EI',
      canonicalUrl: 'https://www.youtube.com/shorts/VpW4T7e34EI',
      stage1: { badge: 'EXECUTED', active: true, text: 'Empty caption; fetched Turkish ASR subtitles (1533 chars >= 150). Creator: Hurda Lab (72.0s).' },
      stage2: { badge: 'SKIPPED', active: false, text: 'Skipped because Stage 1 subtitles met the text threshold without downloading audio.' },
      stage3: { badge: 'SKIPPED', active: false, text: 'Skipped; no frame extraction needed.' },
      outputPath: 'sources/reels/yt_VpW4T7e34EI.json (verified Groq synthesis)',
      outputContent: JSON.stringify({
        shortcode: 'yt_VpW4T7e34EI',
        url: 'https://www.youtube.com/shorts/VpW4T7e34EI',
        creator: 'Hurda Lab',
        title: 'kart\u0131n kurumas\u0131n\u0131 bekliyorum   #electronic #arduino',
        duration: 72.0,
        upload_date: '20261030',
        transcript_source: 'subtitles',
        steps_used: ['metadata', 'subtitles'],
        warnings: [],
        note_path: 'learning/arduino-karti-bakim-onarim.md',
        synthesis_metrics: {
          provider: 'groq',
          model: 'openai/gpt-oss-120b',
          prompt_tokens: 1571,
          completion_tokens: 739,
          total_tokens: 2310,
          retries: 0
        }
      }, null, 2)
    },
    tt76: {
      shortcode: 'tt_7684682826159049991',
      rawUrl: 'https://www.tiktok.com/@kodkatman/video/7684682826159049991',
      canonicalUrl: 'https://www.tiktok.com/@_/video/7684682826159049991',
      stage1: { badge: 'EXECUTED', active: true, text: 'Caption is 69 chars (< 150) and subtitles are empty. Creator: kodkatman (29.0s).' },
      stage2: { badge: 'EXECUTED', active: true, text: 'Transcribed audio via Groq whisper-large-v3-turbo (383 chars Turkish transcript).' },
      stage3: { badge: 'SKIPPED', active: false, text: 'Skipped once spoken transcript met min_transcript_chars (40).' },
      outputPath: 'sources/reels/tt_7684682826159049991.json (verified Groq synthesis)',
      outputContent: JSON.stringify({
        shortcode: 'tt_7684682826159049991',
        url: 'https://www.tiktok.com/@_/video/7684682826159049991',
        creator: 'kodkatman',
        caption: 'ESP32 ile EMO Robot Yap\u0131yoruz 1. #robot #emo #kendinyap #esp32 #maker',
        duration: 29.0,
        upload_date: '20260912',
        transcript_source: 'groq',
        steps_used: ['metadata', 'whisper:groq'],
        warnings: [],
        note_path: 'projects/esp32-emo-robot-yapimi.md',
        synthesis_metrics: {
          provider: 'groq',
          model: 'openai/gpt-oss-120b',
          prompt_tokens: 1256,
          completion_tokens: 607,
          total_tokens: 1863,
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

// 5. Client-side i18n (en, tr, fr, de, es)
(() => {
  const I18N = {
    en: {
      'nav.pipeline': 'Pipeline',
      'nav.sandbox': 'Interactive Sandbox',
      'nav.interfaces': 'Interfaces',
      'nav.guardrails': 'Vault Rules',
      'nav.quickstart': 'Quick Start',
      'nav.docs': 'Docs',
      'hero.title': 'Saved Short-Form Videos to Obsidian Atomic Notes',
      'hero.lead': 'A local-first pipeline that converts saved Instagram Reels, YouTube Shorts, and TikTok videos via captions, Whisper speech transcripts, and Gemini Vision OCR into deduplicated Markdown notes inside an existing 3-layer Obsidian LLM Wiki vault.',
      'hero.ctaSandbox': 'Inspect Live Sandbox',
      'hero.ctaDemo': 'Watch Demo Video',
      'hero.panelTitle': '4-Stage Pipeline',
      'pipeline.kicker': 'Cost-Aware Extraction',
      'pipeline.title': 'Escalates to audio and vision only when text is missing',
      'pipeline.desc1': 'Every item moves through a 3-stage waterfall. Extracted payloads are stored in',
      'pipeline.desc2': ', and raw media files never enter the vault.',
      'sandbox.kicker': 'Verified Walkthroughs',
      'sandbox.title': 'Trace real Reels, Shorts & TikTok videos through the pipeline',
      'sandbox.desc1': 'Select one of the six tested URLs from',
      'sandbox.desc2': 'to inspect URL normalization, stage routing, and verified output behavior.',
      'interfaces.kicker': 'Six Interfaces',
      'interfaces.title': 'Run from terminal, browser extension, MCP client, Python script, or Telegram',
      'interfaces.desc': 'Every entry point shares the same queue, deduplication index, and vault writer. Use arrow keys or click a tab to inspect each interface.',
      'guardrails.kicker': 'Vault Enforcement',
      'guardrails.title': 'Validation guarantees before writing to disk',
      'guardrails.desc': 'Model output is treated as untrusted input and normalized against your vault schema before any file is written.',
      'quickstart.kicker': 'Setup',
      'quickstart.title': 'Quick Start',
      'quickstart.desc1': 'Requires Python 3.10 or newer and',
      'quickstart.desc2': 'on your PATH for audio or frame fallbacks.',
      'quickstart.step1': 'Install via PyPI, Homebrew, or source',
      'quickstart.step2': 'Configure vault path and Instagram cookies',
      'quickstart.step3': 'Add API keys and verify configuration',
      'docs.kicker': 'Guides & Reference',
      'docs.title': 'Documentation',
      'docs.desc': 'Full operational guides covering provider setup, background scheduling, offline capture workflows, v1 compatibility, and diagnostics.',
      'copy.default': 'Copy',
      'copy.done': 'Copied',
    },
    tr: {
      'nav.pipeline': 'Akış',
      'nav.sandbox': 'Etkileşimli Örnekler',
      'nav.interfaces': 'Arayüzler',
      'nav.guardrails': 'Kasa Kuralları',
      'nav.quickstart': 'Hızlı Başlangıç',
      'nav.docs': 'Dokümanlar',
      'hero.title': 'Kısa Videoları Obsidian Atomik Notlarına Dönüştürün',
      'hero.lead': 'Kaydedilen Instagram Reels, YouTube Shorts ve TikTok videolarını altyazı, Whisper konuşma çözümü ve Gemini Vision OCR ile mevcut 3 katmanlı Obsidian LLM Wiki kasanızda tekilleştirilmiş Markdown notlarına çeviren yerel öncelikli hat.',
      'hero.ctaSandbox': 'Canlı Örneği İncele',
      'hero.ctaDemo': 'Tanıtım Videosunu İzle',
      'hero.panelTitle': '4 Aşamalı Akış',
      'pipeline.kicker': 'Maliyet Bilinçli Çıkarım',
      'pipeline.title': 'Yalnızca metin eksik olduğunda ses ve görüntüye geçer',
      'pipeline.desc1': 'Her öğe 3 aşamalı şelaleden geçer. Çıkarılan veriler',
      'pipeline.desc2': ' içinde saklanır ve ham medya dosyaları kasaya asla girmez.',
      'sandbox.kicker': 'Doğrulanmış Senaryolar',
      'sandbox.title': 'Gerçek Reels, Shorts ve TikTok videolarını hatta izleyin',
      'sandbox.desc1': 'URL normalizasyonunu, aşama yönlendirmesini ve doğrulanmış çıktı davranışını incelemek için',
      'sandbox.desc2': ' içindeki altı test edilmiş URL\u2019den birini seçin.',
      'interfaces.kicker': 'Altı Arayüz',
      'interfaces.title': 'Terminal, tarayıcı eklentisi, MCP istemcisi, Python betiği veya Telegram ile çalıştırın',
      'interfaces.desc': 'Her giriş noktası aynı kuyruğu, tekilleştirme dizinini ve kasa yazıcısını paylaşır. Her arayüzü incelemek için ok tuşlarını kullanın veya bir sekmeye tıklayın.',
      'guardrails.kicker': 'Kasa Denetimi',
      'guardrails.title': 'Diske yazmadan önce doğrulama garantileri',
      'guardrails.desc': 'Model çıktısı güvenilmeyen veri olarak ele alınır ve dosya yazılmadan önce kasa şemanıza göre normalize edilir.',
      'quickstart.kicker': 'Kurulum',
      'quickstart.title': 'Hızlı Başlangıç',
      'quickstart.desc1': 'Ses ve kare OCR yedekleri için Python 3.10+ ve PATH üzerinde',
      'quickstart.desc2': ' gereklidir.',
      'quickstart.step1': 'PyPI, Homebrew veya kaynaktan kurun',
      'quickstart.step2': 'Kasa yolunu ve Instagram çerezlerini yapılandırın',
      'quickstart.step3': 'API anahtarlarını ekleyin ve yapılandırmayı doğrulayın',
      'docs.kicker': 'Kılavuzlar ve Referans',
      'docs.title': 'Dokümantasyon',
      'docs.desc': 'Sağlayıcı kurulumu, arka plan zamanlaması, çevrimdışı yakalama, v1 uyumluluğu ve tanılama konularını kapsayan tam operasyon kılavuzları.',
      'copy.default': 'Kopyala',
      'copy.done': 'Kopyalandı',
    },
    fr: {
      'nav.pipeline': 'Pipeline',
      'nav.sandbox': 'Bac à sable',
      'nav.interfaces': 'Interfaces',
      'nav.guardrails': 'Règles du coffre',
      'nav.quickstart': 'Démarrage',
      'nav.docs': 'Documentation',
      'hero.title': 'Vidéos courtes sauvegardées vers notes atomiques Obsidian',
      'hero.lead': 'Pipeline local convertissant vos Instagram Reels, YouTube Shorts et TikTok sauvegardés via légendes, transcription Whisper et OCR Gemini Vision en notes Markdown dédupliquées dans un coffre Obsidian LLM Wiki à 3 couches.',
      'hero.ctaSandbox': 'Explorer le bac à sable',
      'hero.ctaDemo': 'Voir la démo vidéo',
      'hero.panelTitle': 'Pipeline en 4 étapes',
      'pipeline.kicker': 'Extraction économique',
      'pipeline.title': 'N\u2019active l\u2019audio et la vision que lorsque le texte manque',
      'pipeline.desc1': 'Chaque élément traverse une cascade en 3 étapes. Les données extraites sont enregistrées dans',
      'pipeline.desc2': ', et aucun fichier média brut n\u2019entre dans le coffre.',
      'sandbox.kicker': 'Parcours vérifiés',
      'sandbox.title': 'Tracez de vrais Reels, Shorts et TikTok dans le pipeline',
      'sandbox.desc1': 'Sélectionnez l\u2019une des six URL testées dans',
      'sandbox.desc2': 'pour inspecter la normalisation, le routage et le résultat vérifié.',
      'interfaces.kicker': 'Six interfaces',
      'interfaces.title': 'Exécutez via terminal, extension navigateur, client MCP, script Python ou Telegram',
      'interfaces.desc': 'Chaque point d\u2019entrée partage la même file, l\u2019index de déduplication et l\u2019éditeur de coffre. Utilisez les flèches ou cliquez sur un onglet.',
      'guardrails.kicker': 'Contrôle du coffre',
      'guardrails.title': 'Garanties de validation avant écriture sur disque',
      'guardrails.desc': 'La sortie du modèle est traitée comme non fiable et normalisée selon le schéma de votre coffre avant toute écriture.',
      'quickstart.kicker': 'Installation',
      'quickstart.title': 'Démarrage rapide',
      'quickstart.desc1': 'Nécessite Python 3.10 ou plus récent et',
      'quickstart.desc2': 'dans le PATH pour les replis audio ou image.',
      'quickstart.step1': 'Installer via PyPI, Homebrew ou les sources',
      'quickstart.step2': 'Configurer le chemin du coffre et les cookies Instagram',
      'quickstart.step3': 'Ajouter les clés API et vérifier la configuration',
      'docs.kicker': 'Guides & Référence',
      'docs.title': 'Documentation',
      'docs.desc': 'Guides complets sur les fournisseurs, la planification, la capture hors ligne, la compatibilité v1 et le diagnostic.',
      'copy.default': 'Copier',
      'copy.done': 'Copié',
    },
    de: {
      'nav.pipeline': 'Pipeline',
      'nav.sandbox': 'Interaktive Sandbox',
      'nav.interfaces': 'Schnittstellen',
      'nav.guardrails': 'Tresor-Regeln',
      'nav.quickstart': 'Schnellstart',
      'nav.docs': 'Dokumentation',
      'hero.title': 'Gespeicherte Kurzvideos als atomare Obsidian-Notizen',
      'hero.lead': 'Eine Local-First-Pipeline, die gespeicherte Instagram Reels, YouTube Shorts und TikTok-Videos über Untertitel, Whisper-Transkription und Gemini Vision OCR als deduplizierte Markdown-Notizen in Ihren 3-Schichten-Obsidian-Vault schreibt.',
      'hero.ctaSandbox': 'Live-Sandbox ansehen',
      'hero.ctaDemo': 'Demo-Video ansehen',
      'hero.panelTitle': '4-Stufen-Pipeline',
      'pipeline.kicker': 'Kostenbewusste Extraktion',
      'pipeline.title': 'Eskaliert nur zu Audio und Vision, wenn Text fehlt',
      'pipeline.desc1': 'Jedes Element durchläuft eine 3-stufige Kaskade. Extrahierte Daten werden in',
      'pipeline.desc2': ' gespeichert; Mediendateien gelangen nie in den Vault.',
      'sandbox.kicker': 'Verifizierte Durchläufe',
      'sandbox.title': 'Echte Reels, Shorts & TikTok-Videos in der Pipeline verfolgen',
      'sandbox.desc1': 'Wählen Sie eine der sechs getesteten URLs aus',
      'sandbox.desc2': ', um Normalisierung, Stufen-Routing und Ausgabe zu prüfen.',
      'interfaces.kicker': 'Sechs Schnittstellen',
      'interfaces.title': 'Per Terminal, Browser-Erweiterung, MCP-Client, Python-Skript oder Telegram starten',
      'interfaces.desc': 'Jeder Einstiegspunkt nutzt dieselbe Warteschlange, den Deduplizierungsindex und den Vault-Writer. Nutzen Sie Pfeiltasten oder Tabs.',
      'guardrails.kicker': 'Vault-Prüfung',
      'guardrails.title': 'Validierungsgarantien vor dem Schreiben auf die Festplatte',
      'guardrails.desc': 'Modellantworten gelten als nicht vertrauenswürdig und werden vor dem Speichern gegen Ihr Vault-Schema normalisiert.',
      'quickstart.kicker': 'Einrichtung',
      'quickstart.title': 'Schnellstart',
      'quickstart.desc1': 'Erfordert Python 3.10 oder neuer sowie',
      'quickstart.desc2': 'im PATH für Audio- und Frame-Fallbacks.',
      'quickstart.step1': 'Über PyPI, Homebrew oder Quellcode installieren',
      'quickstart.step2': 'Vault-Pfad und Instagram-Cookies konfigurieren',
      'quickstart.step3': 'API-Schlüssel hinzufügen und Konfiguration prüfen',
      'docs.kicker': 'Anleitungen & Referenz',
      'docs.title': 'Dokumentation',
      'docs.desc': 'Vollständige Anleitungen zu Anbietern, Hintergrundplanung, Offline-Erfassung, v1-Kompatibilität und Diagnose.',
      'copy.default': 'Kopieren',
      'copy.done': 'Kopiert',
    },
    es: {
      'nav.pipeline': 'Pipeline',
      'nav.sandbox': 'Sandbox Interactivo',
      'nav.interfaces': 'Interfaces',
      'nav.guardrails': 'Reglas de Bóveda',
      'nav.quickstart': 'Inicio Rápido',
      'nav.docs': 'Documentación',
      'hero.title': 'Videos cortos guardados a notas atómicas en Obsidian',
      'hero.lead': 'Pipeline local que convierte Instagram Reels, YouTube Shorts y videos de TikTok guardados mediante subtítulos, transcripción Whisper y Gemini Vision OCR en notas Markdown deduplicadas dentro de una bóveda Obsidian LLM Wiki de 3 capas.',
      'hero.ctaSandbox': 'Explorar Sandbox en vivo',
      'hero.ctaDemo': 'Ver video de demostración',
      'hero.panelTitle': 'Pipeline de 4 etapas',
      'pipeline.kicker': 'Extracción eficiente',
      'pipeline.title': 'Solo recurre a audio y visión cuando falta texto',
      'pipeline.desc1': 'Cada elemento pasa por una cascada de 3 etapas. Los datos extraídos se guardan en',
      'pipeline.desc2': ', y ningún archivo multimedia entra en la bóveda.',
      'sandbox.kicker': 'Recorridos verificados',
      'sandbox.title': 'Rastrea Reels, Shorts y TikTok reales en el pipeline',
      'sandbox.desc1': 'Selecciona una de las seis URL probadas de',
      'sandbox.desc2': 'para inspeccionar normalización, enrutamiento y salida verificada.',
      'interfaces.kicker': 'Seis interfaces',
      'interfaces.title': 'Ejecuta desde terminal, extensión de navegador, cliente MCP, script Python o Telegram',
      'interfaces.desc': 'Cada punto de entrada comparte la misma cola, índice de deduplicación y escritor. Usa flechas o haz clic en una pestaña.',
      'guardrails.kicker': 'Control de bóveda',
      'guardrails.title': 'Garantías de validación antes de escribir en disco',
      'guardrails.desc': 'La salida del modelo se trata como entrada no confiable y se normaliza contra el esquema de tu bóveda antes de guardar.',
      'quickstart.kicker': 'Configuración',
      'quickstart.title': 'Inicio rápido',
      'quickstart.desc1': 'Requiere Python 3.10 o superior y',
      'quickstart.desc2': 'en PATH para respaldos de audio o fotogramas.',
      'quickstart.step1': 'Instalar mediante PyPI, Homebrew o código fuente',
      'quickstart.step2': 'Configurar ruta de la bóveda y cookies de Instagram',
      'quickstart.step3': 'Agregar claves API y verificar configuración',
      'docs.kicker': 'Guías y Referencia',
      'docs.title': 'Documentación',
      'docs.desc': 'Guías completas sobre proveedores, programación en segundo plano, captura sin conexión, compatibilidad v1 y diagnóstico.',
      'copy.default': 'Copiar',
      'copy.done': 'Copiado',
    },
  };

  const SUPPORTED = new Set(Object.keys(I18N));
  const select = document.getElementById('langSelect');
  if (!select) return;

  function detectInitialLang() {
    const param = new URLSearchParams(window.location.search).get('lang');
    if (param && SUPPORTED.has(param)) return param;
    try {
      const saved = localStorage.getItem('lang');
      if (saved && SUPPORTED.has(saved)) return saved;
    } catch {}
    const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return SUPPORTED.has(browser) ? browser : 'en';
  }

  function applyLang(lang) {
    const chosen = SUPPORTED.has(lang) ? lang : 'en';
    const dict = I18N[chosen];
    document.documentElement.lang = chosen;
    select.value = chosen;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (key && Object.prototype.hasOwnProperty.call(dict, key)) {
        el.textContent = dict[key];
      }
    });
  }

  select.addEventListener('change', () => {
    const chosen = select.value;
    try {
      localStorage.setItem('lang', chosen);
    } catch {}
    applyLang(chosen);
  });

  window.addEventListener('storage', (event) => {
    if (event.key === 'lang' && event.newValue) {
      applyLang(event.newValue);
    }
  });

  applyLang(detectInitialLang());
})();
