document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash-close').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  const toast = document.getElementById('statusToast');
  const showToast = (message, isError = false) => {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle('error', isError);
    toast.classList.add('show');
    window.setTimeout(() => toast.classList.remove('show'), 3600);
  };

  const reminderNote = document.querySelector('.planner-aside .fine-print');
  if (reminderNote && 'Notification' in window) {
    const reminderButton = document.createElement('button');
    reminderButton.type = 'button';
    reminderButton.className = 'button button-secondary button-wide';
    reminderButton.textContent = 'Enable browser reminders';
    reminderNote.before(reminderButton);
    reminderButton.addEventListener('click', async () => {
      let permission = Notification.permission;
      if (permission === 'default') permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        showToast('Browser reminders are off. Change notification permission in your browser settings.', true);
        return;
      }
      try {
        const response = await fetch('/planner/reminders');
        if (!response.ok) throw new Error('Could not load reminders.');
        const { reminders } = await response.json();
        const now = Date.now();
        let scheduled = 0;
        reminders.forEach((reminder) => {
          const delay = new Date(reminder.deadline).getTime() - now;
          if (delay > 0 && delay <= 2147000000) {
            window.setTimeout(() => {
              if (Notification.permission === 'granted') {
                new Notification(reminder.title, { body: `${reminder.kind} deadline is now.` });
              }
            }, delay);
            scheduled += 1;
          }
        });
        showToast(scheduled ? `${scheduled} reminder${scheduled === 1 ? '' : 's'} set while this page stays open.` : 'No future deadlines to remind you about.');
      } catch {
        showToast('Could not set browser reminders. Your planner items are still saved.', true);
      }
    });
    reminderNote.textContent = 'Optional alerts use browser permission and fire only while this page stays open. No background notifications are sent.';
  }

  document.querySelectorAll('[data-status-form]').forEach((select) => {
    select.dataset.previousStatus = select.value;
    select.addEventListener('change', async () => {
      const previousStatus = select.dataset.previousStatus || 'Planned';
      let grade = select.form.querySelector('input[name="grade"]');
      if (!grade) {
        grade = document.createElement('input');
        grade.type = 'hidden';
        grade.name = 'grade';
        select.form.append(grade);
      }
      if (select.value === 'Completed') {
        const enteredGrade = window.prompt('Optional grade for this subject. Leave blank if you do not record grades.');
        if (enteredGrade === null) {
          select.value = previousStatus;
          return;
        }
        grade.value = enteredGrade.trim().slice(0, 20);
      }
      const form = select.form;
      const body = new FormData(form);
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch' },
          body,
        });
        const result = await response.json();
        if (!response.ok) {
          select.value = previousStatus;
          const details = result.missing?.length ? ` Missing: ${result.missing.join(', ')}.` : '';
          showToast(`${result.error || 'Could not update status.'}${details}`, true);
          return;
        }
        select.dataset.previousStatus = result.status;
        showToast(`Subject marked ${result.status.toLowerCase()}.`);
      } catch {
        select.value = previousStatus;
        showToast('Connection issue. Your status was not changed.', true);
      }
    });
  });

  document.querySelectorAll('[data-autosubmit]').forEach((select) => {
    select.addEventListener('change', () => select.form.requestSubmit());
  });

  const canvas = document.getElementById('progressChart');
  if (canvas && window.Chart && window.degreePathProgress) {
    const progress = window.degreePathProgress;
    new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Completed', 'Remaining'],
        datasets: [{ data: [progress.completed, progress.remaining], backgroundColor: ['#2768dc', '#dce5f0'], borderWidth: 0, hoverOffset: 3 }],
      },
      options: { cutout: '79%', plugins: { legend: { display: false }, tooltip: { enabled: true } }, animation: { duration: 650 } },
    });
  }
});