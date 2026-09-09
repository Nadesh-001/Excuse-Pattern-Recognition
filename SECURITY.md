## Security Policy

### Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 9.5.x   | ✅ Yes             |
| < 9.0   | ❌ No              |

### Reporting a Vulnerability

If you discover a security vulnerability, please **do NOT** open a public GitHub Issue.

Instead, please report it by emailing the maintainers directly. You should expect:
- A response within **48 hours** acknowledging the report.
- A status update within **7 days** on the investigation.
- A fix and public disclosure after the patch is verified.

### Security Considerations

- **Never commit** your `.env` file or any credentials.
- The project uses **parameterized SQL queries** to prevent injection attacks.
- **CSRF tokens** are validated on all state-changing requests.
- User passwords are hashed with `werkzeug.security`.

### Known Security Measures

- Row Level Security (RLS) on Supabase PostgreSQL
- Session-based authentication with secure cookies
- Input sanitization and template auto-escaping (Jinja2)
- Role-based authorization on every protected route
