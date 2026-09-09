# Contributing to Excuse Pattern Recognition AI

Thank you for your interest in contributing to EPAI! This document provides guidelines for contributing to this project.

## 🚀 Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Excuse-Pattern-Recognition.git
   cd Excuse-Pattern-Recognition
   ```
3. **Create a branch** for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🛠️ Development Setup

1. **Install Python 3.8+** and `pip`
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure your `.env`** file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Fill in your database credentials and API keys
   ```
5. **Run the application**:
   ```bash
   python run.py
   ```

## 📋 Code Standards

- Follow **PEP 8** Python style guidelines
- Use descriptive variable and function names
- Add **docstrings** to all new functions and classes
- Keep functions small and focused (single responsibility)
- Write comments for complex AI/ML logic

## 🔀 Submitting Changes

1. **Commit** your changes with a clear message:
   ```bash
   git commit -m "feat: add anomaly detection threshold configuration"
   ```
2. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
3. Open a **Pull Request** on GitHub targeting the `main` branch.

## 🐛 Reporting Issues

When reporting bugs, please include:
- Python version and OS
- Steps to reproduce the issue
- Expected vs. actual behavior
- Relevant error messages or logs

## 💡 Feature Requests

Open an issue with the label `enhancement` and describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives considered

## 📝 License

By contributing, you agree that your contributions will be licensed under the **MIT License**.
