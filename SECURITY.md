# Security Policy

## Reporting a Vulnerability

We take the security of mAIcro seriously. If you believe you have found a security vulnerability, please report it to us as soon as possible.

**How to Report:**
- **Confidential Reporting**: Please email us at [microclubit@gmail.com](mailto:microclubit@gmail.com). 
- **GitHub Security Advisory**: Alternatively, you can use the ["Report a vulnerability"](https://github.com/MicroClub-USTHB/mAIcro/security/advisories/new) button on GitHub.

Please include:
1. A description of the vulnerability.
2. Steps to reproduce the issue.
3. Potential impact.

We will acknowledge your report within 48 hours and provide a timeline for resolution.

---

## Security Best Practices for Users

To keep your mAIcro instance secure, please follow these guidelines:

### 1. Protect Your API Keys
mAIcro relies on several sensitive API keys:
- `GEMINI_API_KEY`
- `QDRANT_API_KEY`
- `DISCORD_BOT_TOKEN`

**Never commit these keys to version control.** Always use the `.env` file (which is included in `.gitignore`) or use a secure secret management service (like GitHub Secrets, AWS Secrets Manager, or HashiCorp Vault).

### 2. Least Privilege (Discord Bot)
When setting up your Discord bot, only grant the minimum required permissions:
- `View Channels`
- `Read Message History`
- `Message Content Intent` (required for RAG functionality)

Avoid granting `Administrator` or other broad permissions unless absolutely necessary for your specific use case.

### 3. Environment Isolation
Use separate API keys and Qdrant collections for development and production environments to prevent accidental data loss or exposure.

### 4. Regular Updates
Regularly pull the latest Docker image (`ghcr.io/microclub-usthb/maicro:latest`) to ensure you have the latest security patches and features.
