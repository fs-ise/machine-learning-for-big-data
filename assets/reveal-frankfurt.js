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

    if (!document.getElementById('fs-slide-footer')) {
      const footer = document.createElement('div');
      footer.id = 'fs-slide-footer';
      footer.innerHTML = '<span class="footer-left">Analytics & Big Data</span><span class="footer-center">Frankfurt School</span><span class="footer-right">Teaching Repository</span>';
      document.body.appendChild(footer);
    }

    if (!document.getElementById('custom-slide-number')) {
      const number = document.createElement('div');
      number.id = 'custom-slide-number';
      document.body.appendChild(number);
    }

    if (!document.getElementById('pdf-download')) {
      const pdf = document.createElement('a');
      pdf.id = 'pdf-download';
      pdf.href = `${window.location.pathname.replace(/\.html$/, '.pdf')}`;
      pdf.textContent = 'Download PDF';
      pdf.setAttribute('download', '');
      document.body.appendChild(pdf);
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
