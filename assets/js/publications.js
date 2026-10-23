(function () {
  'use strict';
  var list = document.getElementById('journal-publications');
  if (!list) return;

  var entries = Array.from(list.querySelectorAll('[data-publication]'));
  var search = document.getElementById('pub-search');
  var year = document.getElementById('pub-year');
  var topic = document.getElementById('pub-topic');
  var count = document.getElementById('pub-count');
  var empty = document.getElementById('no-results');
  var reset = document.getElementById('pub-reset');

  function normalise(text) {
    return text.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  var records = entries.map(function (entry) {
    return {
      element: entry,
      text: normalise(entry.textContent),
      year: entry.dataset.year,
      topics: (entry.dataset.topics || '').split('|').filter(Boolean)
    };
  });

  function addOptions(select, values) {
    values.forEach(function (value) {
      var option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  }

  addOptions(year, Array.from(new Set(records.map(function (r) { return r.year; }))).sort().reverse());
  addOptions(topic, Array.from(new Set(records.reduce(function (all, r) { return all.concat(r.topics); }, []))).sort());

  function filter() {
    var terms = normalise(search.value.trim()).split(/\s+/).filter(Boolean);
    var visible = 0;
    records.forEach(function (record) {
      var show = terms.every(function (term) { return record.text.indexOf(term) !== -1; }) &&
        (!year.value || record.year === year.value) &&
        (!topic.value || record.topics.indexOf(topic.value) !== -1);
      record.element.hidden = !show;
      if (show) visible += 1;
    });
    count.textContent = visible + ' of ' + records.length + ' publications';
    empty.hidden = visible !== 0;
  }

  search.addEventListener('input', filter);
  year.addEventListener('change', filter);
  topic.addEventListener('change', filter);
  reset.addEventListener('click', function () {
    search.value = '';
    year.value = '';
    topic.value = '';
    filter();
    search.focus();
  });
  document.getElementById('publication-filters').hidden = false;
  filter();
})();
