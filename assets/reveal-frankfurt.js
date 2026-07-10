(function () {
  const logoUrl = 'https://raw.githubusercontent.com/fs-ise/analytics-and-big-data/main/assets/fs_logo_blue.svg';

  function currentTitle() {
    const current = Reveal.getCurrentSlide();
    const heading = current && current.querySelector('h1, h2');
    return heading ? heading.textContent.trim() : (document.title || '').replace(/\s+-\s+.*$/, '');
  }

  function updateChrome() {
    const title = document.getElementById('slide-title-display');
    if (title) title.textContent = currentTitle();

    const number = document.getElementById('custom-slide-number');
    if (number && window.Reveal) {
      const indices = Reveal.getIndices();
      const total = Reveal.getTotalSlides();
      number.textContent = `${indices.h + indices.v + 1} / ${total}`;
    }
  }

  function addChrome() {
    if (!document.getElementById('fs-header')) {
      const header = document.createElement('div');
      header.id = 'fs-header';
      header.innerHTML = `<span id="slide-title-display"></span><img src="${logoUrl}" alt="Frankfurt School Logo">`;
      document.body.appendChild(header);
    }

    if (!document.getElementById('custom-slide-number')) {
      const number = document.createElement('div');
      number.id = 'custom-slide-number';
      document.body.appendChild(number);
    }

    updateChrome();
    Reveal.on('slidechanged', updateChrome);
    Reveal.on('ready', updateChrome);
  }

  if (window.Reveal) {
    addChrome();
  } else {
    document.addEventListener('DOMContentLoaded', addChrome);
  }
}());
