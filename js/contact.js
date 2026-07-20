/* ============================================
   PAT Orbit — Contact Form Script
   Form validation, API submission, fallback
   ============================================ */

(function () {
  'use strict';

  const contactForm = document.querySelector('.contact-form');
  if (!contactForm) return;

  const submissionStatus = document.getElementById('submission-status');
  const submitButton = contactForm.querySelector('button[type="submit"]');
  const apiUrl = contactForm.dataset.apiUrl || '';
  const mailtoAddress = contactForm.dataset.mailto || '';

  /* ---- Helper: Build mailto fallback URL ---- */
  const buildMailtoUrl = (payload) => {
    const subject = `Project enquiry from ${payload.name}`;
    const body = [
      `Name: ${payload.name}`,
      `Email: ${payload.email}`,
      `Project type: ${payload.project_type}`,
      `Timeline: ${payload.timeline || 'Not provided'}`,
      `Budget: ${payload.budget || 'Not provided'}`,
      '',
      payload.message
    ].join('\n');

    return `mailto:${mailtoAddress}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  /* ---- Helper: Check if API is reachable ---- */
  const isLocalApiAvailable = () => {
    const isLocalPage = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    return !apiUrl.includes('localhost') || isLocalPage;
  };

  /* ---- Helper: Show status message ---- */
  const showStatus = (type, message, isHTML = false) => {
    submissionStatus.hidden = false;
    submissionStatus.className = `submission-status status-${type}`;
    if (isHTML) {
      submissionStatus.innerHTML = message;
    } else {
      submissionStatus.textContent = message;
    }
  };

  /* ---- Helper: Validate form fields ---- */
  const getValidationErrors = (data) => {
    const errors = [];
    if (!data.name || data.name.trim().length < 2) {
      errors.push('Please enter your name (at least 2 characters).');
    }
    if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
      errors.push('Please enter a valid email address.');
    }
    if (!data.project_type) {
      errors.push('Please select a project type.');
    }
    if (!data.message || data.message.trim().length < 10) {
      errors.push('Please describe your project (at least 10 characters).');
    }
    return errors;
  };

  /* ---- Helper: Show field validation errors ---- */
  const showFieldErrors = (errors) => {
    // Clear previous errors
    document.querySelectorAll('.error-message').forEach(el => el.remove());
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    if (errors.length === 0) return;

    const errorHTML = errors.map(err => `<div class="error-message">${err}</div>`).join('');
    showStatus('error', errorHTML, true);
  };

  /* ---- Helper: Set loading state ---- */
  const setLoading = (loading) => {
    if (!submitButton) return;
    submitButton.disabled = loading;
    submitButton.classList.toggle('loading', loading);
    submitButton.textContent = loading ? 'Sending...' : 'Send Message';
  };

  /* ---- Main: Form Submit Handler ---- */
  contactForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(contactForm);
    const payload = {
      name: formData.get('name')?.trim() || '',
      email: formData.get('email')?.trim() || '',
      project_type: formData.get('project-type') || '',
      message: formData.get('message')?.trim() || '',
      timeline: formData.get('timeline')?.trim() || null,
      budget: formData.get('budget')?.trim() || null
    };

    // Validate
    const errors = getValidationErrors(payload);
    if (errors.length > 0) {
      showFieldErrors(errors);
      return;
    }

    // Clear field errors and show sending
    document.querySelectorAll('.error-message').forEach(el => el.remove());
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    showStatus('info', 'Sending your enquiry...');
    setLoading(true);

    try {
      // If API is not available locally, fall back to mailto
      if (!isLocalApiAvailable()) {
        window.location.href = buildMailtoUrl(payload);
        showStatus('info', 'Opening your email app so you can send the enquiry directly.');
        setLoading(false);
        return;
      }

      // Send to API
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      // Success
      contactForm.reset();
      showStatus('success', 'Thanks. Your enquiry has been saved and I will reply soon.');
    } catch (error) {
      console.warn('API unavailable, falling back to mailto:', error.message);
      window.location.href = buildMailtoUrl(payload);
      showStatus('info', 'Could not reach the server. Opening your email app instead.');
    } finally {
      setLoading(false);
    }
  });

  /* ---- Real-time field validation ---- */
  contactForm.querySelectorAll('input, select, textarea').forEach(field => {
    field.addEventListener('blur', () => {
      if (field.value.trim()) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
      } else {
        field.classList.remove('is-valid');
        if (field.hasAttribute('required')) {
          field.classList.add('is-invalid');
        }
      }
    });

    field.addEventListener('input', () => {
      if (field.value.trim()) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
      } else {
        field.classList.remove('is-valid');
      }
    });
  });

  console.log('💬 PAT Orbit — contact form initialized');
})();
