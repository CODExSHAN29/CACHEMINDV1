# Contributing to CacheMind

Thank you for your interest in contributing to CacheMind! We welcome contributions to help make AI inference faster, safer, and more cost-effective.

---

## 🚀 Getting Started

### 1. Fork & Clone
```bash
git clone https://github.com/<your-username>/cachemind.git
cd cachemind
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Environment Configuration
```bash
cp .env.example .env
```

---

## 🧪 Testing & Verification

We enforce a 100% pass rate on all unit and integration tests.

```bash
# Run complete test suite
pytest -v

# Run live system verification
python scripts/verify_live.py

# Run latency benchmark suite
python scripts/benchmark_latency.py
```

---

## 📋 Development Guidelines

- **Code Style**: Follow PEP 8 and use type annotations for all function signatures.
- **Testing**: Every new feature or bug fix must include corresponding tests in `backend/tests/unit/` or `backend/tests/integration/`.
- **Security & Privacy**: Never log raw PII or secret keys. Verify that PII masking guards remain intact.
- **Commits**: Write clear, descriptive commit messages following Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).

---

## 📬 Submitting a Pull Request

1. Create a descriptive feature branch: `git checkout -b feat/my-new-feature`
2. Ensure all tests pass: `pytest -v`
3. Commit your changes and push to your fork: `git push origin feat/my-new-feature`
4. Open a Pull Request on GitHub against `main`. Fill out the PR template checklist.
