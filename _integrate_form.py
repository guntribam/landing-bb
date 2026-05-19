"""One-shot integration script. Splices the Brevo form (form.html) into index.html
as a lead-capture modal triggered by the WhatsApp CTAs. Detects successful submission
via MutationObserver on #success-message and redirects to /zap."""

import sys


def read(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(p, c):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(c)


form_lines = read("form.html").split("\n")

# Sanity-check anchors (1-indexed lines from earlier read)
assert form_lines[5].strip() == "<style>", f"line 6 expected <style>, got: {form_lines[5][:50]!r}"
assert form_lines[59].strip() == "</style>", f"line 60 expected </style>, got: {form_lines[59][:50]!r}"
assert form_lines[60].strip().startswith("<link"), f"line 61 expected <link>, got: {form_lines[60][:50]!r}"
assert form_lines[71].lstrip().startswith('<div class="sib-form"'), f"line 72: {form_lines[71][:50]!r}"
assert form_lines[1273].strip() == "</div>", f"line 1274: {form_lines[1273][:50]!r}"
assert form_lines[1277].strip() == "<script>", f"line 1278: {form_lines[1277][:50]!r}"
assert "main.js" in form_lines[1321], f"line 1322: {form_lines[1321][:80]!r}"

brevo_style_inner = "\n".join(form_lines[6:59])
brevo_link = form_lines[60].strip()
form_body = "\n".join(form_lines[71:1274])
brevo_scripts = "\n".join(form_lines[1277:1322])

modal_css = """
/* ============ LEAD MODAL ============ */
.lead-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.78);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
  z-index: 200;
  display: none;
  align-items: flex-start;
  justify-content: center;
  padding: 32px 16px;
  overflow-y: auto;
}
.lead-modal-overlay.open { display: flex; }
.lead-modal {
  background: #fafaf7;
  color: #15181c;
  border-radius: 6px;
  max-width: 620px;
  width: 100%;
  position: relative;
  margin: auto;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(10, 117, 238, 0.35);
  animation: modalIn 0.26s cubic-bezier(0.2, 0.7, 0.2, 1);
}
@keyframes modalIn {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
.lead-modal-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 36px;
  height: 36px;
  background: transparent;
  border: 1px solid #d0cdc6;
  border-radius: 50%;
  color: #6b6860;
  font-family: var(--sans);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s ease, color 0.2s ease;
  z-index: 2;
}
.lead-modal-close:hover { border-color: var(--accent); color: var(--accent); }
.lead-modal-header { padding: 32px 36px 14px; text-align: left; }
.lead-modal-eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-bottom: 12px;
}
.lead-modal h3 {
  font-family: var(--serif);
  font-size: 28px;
  font-weight: 600;
  color: #15181c;
  margin-bottom: 8px;
  letter-spacing: -0.01em;
  line-height: 1.1;
}
.lead-modal-sub { font-size: 15px; color: #4a4740; line-height: 1.5; }
.lead-modal-body { padding: 0 18px 24px; }
@media (max-width: 600px) {
  .lead-modal-header { padding: 26px 22px 10px; }
  .lead-modal-body { padding: 0 8px 18px; }
  .lead-modal h3 { font-size: 24px; }
}

/* Brevo form-embed styles (from form.html) */
"""

modal_html = f"""
<!-- ============ LEAD MODAL ============ -->
<div class="lead-modal-overlay" id="lead-modal" aria-hidden="true" role="dialog" aria-labelledby="lead-modal-title">
  <div class="lead-modal">
    <button type="button" class="lead-modal-close" aria-label="Fechar">&times;</button>
    <div class="lead-modal-header">
      <div class="lead-modal-eyebrow">PRÉ-LANÇAMENTO TURMA 2 · BB</div>
      <h3 id="lead-modal-title">Antes de entrar no grupo</h3>
      <p class="lead-modal-sub">Deixa seu contato — eu te aviso por e-mail dos PDFs e das lives do cronograma.</p>
    </div>
    <div class="lead-modal-body">
{form_body}
    </div>
  </div>
</div>

"""

interceptor_js = """

    /* === LEAD MODAL === */
    (() => {
      const modal = document.getElementById('lead-modal');
      if (!modal) return;
      const ctas = ['cta-hero', 'cta-final'].map(id => document.getElementById(id)).filter(Boolean);
      const closeBtn = modal.querySelector('.lead-modal-close');
      const successPanel = document.getElementById('success-message');
      const ZAP_URL = 'https://link.devestavel.com.br/zap';

      function openModal(e) {
        if (e) e.preventDefault();
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        try { fbq('track', 'InitiateCheckout'); } catch (_) {}
      }
      function closeModal() {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
      }

      ctas.forEach(b => b.addEventListener('click', openModal));
      if (closeBtn) closeBtn.addEventListener('click', closeModal);
      modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
      });

      // Detect successful Brevo submission and redirect to the WhatsApp shortlink.
      if (successPanel) {
        let redirected = false;
        const obs = new MutationObserver(() => {
          if (redirected) return;
          const visible = getComputedStyle(successPanel).display !== 'none';
          if (visible) {
            redirected = true;
            try { fbq('track', 'Lead'); } catch (_) {}
            setTimeout(() => { window.location.href = ZAP_URL; }, 1200);
          }
        });
        obs.observe(successPanel, { attributes: true, attributeFilter: ['style', 'class'] });
      }
    })();
"""

idx = read("index.html")

# Idempotency guard
if "lead-modal-overlay" in idx:
    print("Already integrated — aborting.")
    sys.exit(1)

# 1) Add modal CSS + Brevo's inline @font-face/etc. before </style>
new_style_chunk = modal_css + brevo_style_inner + "\n"
assert idx.count("</style>") >= 1
idx = idx.replace("</style>", new_style_chunk + "</style>", 1)

# 2) Brevo's stylesheet <link> before </head>
idx = idx.replace("</head>", brevo_link + "\n</head>", 1)

# 3) Modal HTML right before <!-- Meta Pixel Code -->
idx = idx.replace("<!-- Meta Pixel Code -->", modal_html + "<!-- Meta Pixel Code -->", 1)

# 4) Interceptor JS appended inside existing inline <script>, just before </script>
nl = "\r\n" if "\r\n" in idx else "\n"
anchor = f"</script>{nl}    <noscript>"
assert anchor in idx, f"Could not find </script>+<noscript> anchor with sep={nl!r}"
idx = idx.replace(anchor, interceptor_js + anchor, 1)

# 5) Brevo bottom scripts before </body>
idx = idx.replace("</body>", "\n" + brevo_scripts + "\n</body>", 1)

write("index.html", idx)
print("OK — integrated.")
