# Contributing

Contributions are welcome! This section outlines guidelines for contributing to the crypto-microstructure project.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/crypto-microstructure.git
cd crypto-microstructure

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
pip install pytest black flake8 jupyter ipython
```

## Code Style

- Follow PEP 8 (100-character line limit)
- Use type hints on all function signatures
- Write Google-style docstrings with references to academic papers where applicable
- Format code with Black: `black src/ tests/ scripts/`
- Lint with Flake8: `flake8 src/ tests/ scripts/`

## Testing

- Write unit tests for all new features
- Use pytest: `pytest tests/ -v`
- Aim for >80% test coverage on new code
- Test both happy paths and edge cases (empty input, invalid data, etc.)

## Documentation

- Update README.md if adding new features
- Add docstring examples for complex functions
- Include references to academic papers (Kyle 1985, Roll 1984, etc.)
- Keep examples.md current with new usage patterns

## Commits

- Use clear, descriptive commit messages
- Reference issues when applicable: "Fixes #123"
- Keep commits focused on single features/fixes
- Don't commit large data files (.parquet, .csv) — use .gitignore

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run tests: `pytest tests/`
5. Format code: `black src/ tests/`
6. Lint: `flake8 src/ tests/`
7. Commit with clear messages
8. Push to your fork
9. Open a pull request with description of changes

## Areas for Contribution

- [ ] Additional microstructure metrics (Hurst exponent, volatility clustering, etc.)
- [ ] Support for other exchange APIs (FTX, dYdX, etc.)
- [ ] Performance optimizations for large datasets
- [ ] Additional visualization types
- [ ] Extended documentation and tutorials
- [ ] CI/CD pipeline setup (GitHub Actions)
- [ ] Type checking with mypy
- [ ] Statistical tests for metric validation

## Guidelines

1. **Academic rigor**: Cite papers for all metrics, explain theoretical foundations
2. **Clean code**: Readable, well-documented, properly tested
3. **Performance**: Vectorized operations, efficient algorithms
4. **Reproducibility**: Deterministic results, documented random seeds
5. **Accessibility**: Support multiple use cases (research, trading, education)

## Questions?

Open an issue or discussion if you have questions about contributing.

---

Thank you for contributing to better market microstructure research in crypto!
