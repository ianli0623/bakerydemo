(function () {
  'use strict';

  var scaleValues = ['small', 'default', 'large'];
  var scaleClasses = scaleValues.map(function (value) {
    return 'font-scale--' + value;
  });

  function readScale() {
    try {
      var stored = window.localStorage.getItem('semi-e187-font-scale');
      return scaleValues.includes(stored) ? stored : 'default';
    } catch {
      return 'default';
    }
  }

  function applyScale(value, buttons) {
    document.documentElement.dataset.fontScale = value;
    document.documentElement.classList.remove.apply(
      document.documentElement.classList,
      scaleClasses,
    );
    document.documentElement.classList.add('font-scale--' + value);
    buttons.forEach(function (button, index) {
      var buttonValue = ['large', 'default', 'small'][index];
      button.setAttribute('aria-pressed', String(buttonValue === value));
    });
    try {
      window.localStorage.setItem('semi-e187-font-scale', value);
    } catch {
      // Some browsers disable storage for local files; the current page still works.
    }
  }

  function initializeFontControls() {
    var buttons = Array.from(
      document.querySelectorAll('.accessibility-toolbar__controls button'),
    );
    if (buttons.length !== 3) return;

    applyScale(readScale(), buttons);
    buttons.forEach(function (button, index) {
      button.addEventListener('click', function () {
        applyScale(['large', 'default', 'small'][index], buttons);
      });
    });
  }

  function initializeNavigation() {
    var toggle = document.querySelector('.nav-toggle');
    var navigation = document.querySelector('#primary-navigation');
    if (!toggle || !navigation) return;

    var label = toggle.querySelector('.nav-toggle__label');
    var openLabel = label ? label.textContent.trim() : '';
    var closeLabel =
      document.documentElement.lang === 'en' ? 'Close menu' : '關閉選單';

    function setOpen(open) {
      navigation.classList.toggle('site-nav--open', open);
      toggle.setAttribute('aria-expanded', String(open));
      if (label) label.textContent = open ? closeLabel : openLabel;
    }

    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    navigation.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        setOpen(false);
      });
    });
    window.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') setOpen(false);
    });
  }

  function initializeRegistry() {
    var form = document.querySelector('.registry-filters');
    var tableWrap = document.querySelector('.registry-table-wrap');
    if (!form || !tableWrap) return;

    var query = form.querySelector('#registry-query');
    var certificate = form.querySelector('#registry-certificate-status');
    var workflow = form.querySelector('#registry-workflow-status');
    var reset = form.querySelector('button[type="button"]');
    var rows = Array.from(tableWrap.querySelectorAll('tbody tr'));
    var resultCount = document.querySelector('.registry-result-count');
    var empty = document.createElement('p');
    empty.className = 'registry-empty';
    empty.setAttribute('role', 'status');
    empty.textContent =
      document.documentElement.lang === 'en'
        ? 'No matching records.'
        : '查無符合條件的資料。';
    empty.hidden = true;
    tableWrap.insertAdjacentElement('afterend', empty);

    function closeDetails() {
      document.querySelector('#registry-record-detail')?.remove();
      rows.forEach(function (row) {
        row
          .querySelector('.registry-view-button')
          ?.setAttribute('aria-expanded', 'false');
      });
    }

    function applyFilters() {
      closeDetails();
      var text = query.value.trim().toLocaleLowerCase();
      var visible = rows.filter(function (row) {
        var number =
          row.querySelector('th')?.textContent.trim().toLocaleLowerCase() || '';
        var certificateMatches =
          !certificate.value ||
          (certificate.value === 'notEffective' &&
            row.querySelector('.registry-status--certificate'));
        var workflowMatches =
          !workflow.value ||
          row.querySelector('.registry-status--' + workflow.value);
        var show =
          number.includes(text) && certificateMatches && workflowMatches;
        row.hidden = !show;
        return show;
      });

      tableWrap.hidden = visible.length === 0;
      empty.hidden = visible.length !== 0;
      if (resultCount) {
        resultCount.textContent = resultCount.textContent.replace(
          /\d+/,
          visible.length,
        );
      }
    }

    function showDetails(row, button) {
      closeDetails();
      button.setAttribute('aria-expanded', 'true');
      var cells = Array.from(row.querySelectorAll('th, td')).slice(0, -1);
      var section = document.createElement('section');
      section.id = 'registry-record-detail';
      section.className = 'registry-detail';
      section.tabIndex = -1;

      var header = document.createElement('div');
      header.className = 'registry-detail__header';
      var heading = document.createElement('h2');
      heading.textContent = cells[0]?.textContent.trim() || '';
      var close = document.createElement('button');
      close.className = 'registry-view-button';
      close.type = 'button';
      close.textContent =
        document.documentElement.lang === 'en' ? 'Close' : '關閉';
      close.addEventListener('click', closeDetails);
      header.append(heading, close);

      var list = document.createElement('dl');
      list.className = 'registry-detail__grid';
      cells.forEach(function (cell) {
        var item = document.createElement('div');
        var term = document.createElement('dt');
        var description = document.createElement('dd');
        term.textContent = cell.getAttribute('data-label') || '';
        description.textContent = cell.textContent.trim();
        item.append(term, description);
        list.append(item);
      });
      section.append(header, list);
      tableWrap.insertAdjacentElement('afterend', section);
      section.focus();
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      applyFilters();
    });
    reset?.addEventListener('click', function () {
      form.reset();
      applyFilters();
    });
    rows.forEach(function (row) {
      var button = row.querySelector('.registry-view-button');
      button?.addEventListener('click', function () {
        showDetails(row, button);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initializeFontControls();
    initializeNavigation();
    initializeRegistry();
  });
})();
