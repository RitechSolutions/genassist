# Security Policy

## Supported Versions

The following versions of GenAssist are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of GenAssist seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please use one of these methods:

1. **GitHub Security Advisories**: Use the "Report a vulnerability" button in the [Security tab](https://github.com/RitechSolutions/genassist/security/advisories/new) of this repository (preferred)
2. **Email**: Send details to the repository maintainers

### What to Include

When reporting a vulnerability, please provide:

- A clear description of the vulnerability
- Steps to reproduce the issue
- Affected components (frontend, backend, API, database, etc.)
- Potential impact and severity assessment
- Any proof-of-concept code (if applicable)
- Suggested remediation (optional)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Every 7 days until resolution
- **Resolution Target**: Based on severity
  - Critical: 7 days
  - High: 14 days
  - Medium: 30 days
  - Low: 90 days

### After Reporting

1. We will acknowledge receipt of your report
2. We will investigate and validate the issue
3. We will keep you informed of our progress
4. We will work on a fix and coordinate disclosure timing with you
5. We will credit you in the release notes (unless you prefer anonymity)

## Security Considerations for GenAssist

Given that GenAssist handles AI workflows, user data, and integrates with various LLM providers, we pay special attention to:

### Authentication & Authorization
- Secure user authentication mechanisms
- Role-based access control (RBAC)
- API key management and secure storage

### Data Protection
- Encryption of sensitive data at rest and in transit
- Secure handling of conversation data and transcripts
- Protection of AI agent configurations and credentials

### API Security
- Input validation and sanitization
- Rate limiting and abuse prevention
- Secure communication with LLM providers

### Infrastructure
- Container security best practices
- Database security (PostgreSQL)
- Secure environment variable handling

## Security Best Practices for Contributors

When contributing to GenAssist, please follow these guidelines:

### Code Security
- Never commit secrets, API keys, passwords, or credentials
- Use environment variables for all sensitive configuration
- Validate and sanitize all user inputs
- Use parameterized queries to prevent SQL injection
- Escape output to prevent XSS attacks
- Follow the principle of least privilege

### Dependencies
- Keep dependencies up to date
- Review security advisories for dependencies
- Use `npm audit` and `pip audit` to check for vulnerabilities

### Authentication
- Never store passwords in plain text
- Use secure session management
- Implement proper CORS policies

### Environment Files
- Never commit `.env` files
- Use `.env.example` as a template without actual secrets
- Document required environment variables

## Scope

This security policy applies to:

- The GenAssist core repository
- Frontend application (React/TypeScript)
- Backend API (FastAPI/Python)
- Official plugins (React, iOS)
- Associated documentation
- Docker configurations

### Out of Scope

- Third-party dependencies (report to their maintainers)
- Self-hosted instances with custom modifications
- Issues in forked repositories

## Recognition

We appreciate security researchers who help keep GenAssist and its users safe. Contributors who report valid security issues will be:

- Acknowledged in our release notes (with permission)
- Added to our security hall of fame (coming soon)

Thank you for helping us maintain a secure platform for AI workflow management.
