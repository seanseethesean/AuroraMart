Password reset email delivery (development)

Where the password-reset email is written during development

1. Console backend (default)

- The project defaults to Django's console email backend during development.
- Configuration (in `auroramartproj/settings.py`):

  EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

- Behavior: when you trigger a password-reset, Django prints the full email body
  (including the one-time reset link) to the terminal where you started
  `manage.py runserver` (or to the terminal where you ran the management command).

- What to do: check that terminal for a block that starts with "Subject:" and
  contains the reset URL. Copy-and-paste the URL into your browser to continue
  the flow.

2. File-based backend (optional)

- If you prefer files instead of console output, the settings include a
  file-based option. To enable it, set in `settings.py` or your environment:

  EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
  EMAIL_FILE_PATH = BASE_DIR / 'tmp' / 'emails'

- Behavior: Django writes each outgoing email as a file into
  `<project_root>/auroramartproj/tmp/emails/`.

- What to do: open the most-recent file in that directory and look for the
  reset link in the email body. The files are plain text.

3. When no email appears

- Confirm the app is actually using the development settings file (check
  `auroramartproj/settings.py`).
- Confirm a user exists with the email you submitted (password reset only sends to
  registered users).
- If you're running the server in a different terminal/IDE panel, check that
  terminal's output for the console email.

4. If you want real delivery

- Replace the backend with SMTP or a transactional provider and add credentials
  in environment variables. Use `django.core.mail.backends.smtp.EmailBackend`
  and set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, and
  `EMAIL_HOST_PASSWORD`.

Security note

- Keep SMTP credentials out of source control. Use environment variables or a
  secret manager in production. The console/file backends are for local
  development and testing only.
