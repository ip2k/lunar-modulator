// SweetAlert2 owns transient presentation/timers. Refusals stay inline and
// persistent. The original DOM node preserves native buttons and plain text.
import Swal from './vendor/sweetalert2/sweetalert2.esm.min.js';

export function fileNotifications(element) {
  const anchor = document.createComment('file notice');
  element.before(anchor);
  let generation = 0;
  function restore() {
    anchor.before(element);
    element.hidden = true;
    element.setAttribute('role', 'status');
  }
  function dismiss() {
    generation++;
    Swal.close();
    restore();
  }
  function show(transient) {
    element.hidden = false;
    if (!transient) return;
    const current = ++generation;
    element.removeAttribute('role'); // the library popup supplies the live region
    Swal.fire({
      toast: true, position: 'bottom-end', html: element,
      showConfirmButton: false, timer: 10000, returnFocus: false,
      showClass: { popup: '' }, hideClass: { popup: '' },
      customClass: { popup: 'lunar-toast', htmlContainer: 'lunar-toast-content' },
      didOpen(popup) {
        popup.removeAttribute('aria-labelledby'); // no separate title in this toast
        const resume = () => {
          if (!popup.matches(':hover') && !popup.contains(document.activeElement)) Swal.resumeTimer();
        };
        popup.addEventListener('mouseenter', Swal.stopTimer);
        popup.addEventListener('mouseleave', resume);
        popup.addEventListener('focusin', Swal.stopTimer);
        popup.addEventListener('focusout', () => queueMicrotask(resume));
      },
      didClose() { if (current === generation) restore(); },
    });
  }
  return { dismiss, show };
}
