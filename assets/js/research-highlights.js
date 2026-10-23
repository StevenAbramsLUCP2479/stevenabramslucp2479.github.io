(function () {
  'use strict';
  var region = document.getElementById('research-highlights');
  if (!region) return;
  var pool = Array.from(region.querySelectorAll('[data-highlight]'));
  if (pool.length < 2) return;

  // Keep the newest article, then choose a different paper per year each UTC day.
  // The pool comes from Jekyll's publications collection, so new records join automatically.
  var day = Math.floor(Date.now() / 86400000);
  var years = new Map();
  pool.slice(1).forEach(function (slide) {
    var year = slide.dataset.year;
    if (!years.has(year)) years.set(year, []);
    years.get(year).push(slide);
  });
  var slides = [pool[0]];
  years.forEach(function (candidates) {
    slides.push(candidates[day % candidates.length]);
  });

  var controls = region.querySelector('[data-highlights-controls]');
  var toggle = region.querySelector('[data-highlights-toggle]');
  var position = region.querySelector('[data-highlights-position]');
  var announcement = region.querySelector('[data-highlights-announcement]');
  var motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var playing = !motion.matches;
  var hovered = false;
  var index = 0;
  var timer = null;
  var pointerPlaying = null;
  pool.forEach(function (slide) { slide.hidden = true; });
  slides.forEach(function (slide, i) {
    slide.setAttribute('role', 'group');
    slide.setAttribute('aria-roledescription', 'slide');
    slide.setAttribute('aria-label', (i + 1) + ' of ' + slides.length);
  });

  function show(next, announce) {
    slides[index].hidden = true;
    index = (next + slides.length) % slides.length;
    slides[index].hidden = false;
    position.textContent = (index + 1) + ' / ' + slides.length;
    if (announce) announcement.textContent = 'Publication ' + (index + 1) + ' of ' + slides.length + ': ' + slides[index].querySelector('h3').textContent;
  }

  function schedule() {
    window.clearTimeout(timer);
    timer = null;
    toggle.textContent = playing ? 'Pause rotation' : 'Play rotation';
    if (playing && !hovered && !document.hidden) {
      timer = window.setTimeout(function () {
        show(index + 1, false);
        schedule();
      }, 10000);
    }
  }

  function pause() {
    playing = false;
    schedule();
  }

  // Remember pointer intent before focusin pauses rotation.
  toggle.addEventListener('pointerdown', function () { pointerPlaying = playing; });
  toggle.addEventListener('click', function (event) {
    playing = !(event.detail > 0 && pointerPlaying !== null ? pointerPlaying : playing);
    pointerPlaying = null;
    schedule();
  });
  region.querySelector('[data-highlights-previous]').addEventListener('click', function () {
    pause();
    show(index - 1, true);
  });
  region.querySelector('[data-highlights-next]').addEventListener('click', function () {
    pause();
    show(index + 1, true);
  });
  // Stop when a keyboard user enters; never hide the link they are interacting with.
  region.addEventListener('focusin', pause);
  region.addEventListener('mouseenter', function () { hovered = true; schedule(); });
  region.addEventListener('mouseleave', function () { hovered = false; schedule(); });
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', function () { if (motion.matches) pause(); });

  controls.hidden = false;
  region.querySelector('[data-highlights-intro]').hidden = false;
  show(0, false);
  schedule();
})();
