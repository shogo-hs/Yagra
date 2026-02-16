# Yagra Documentation

This directory contains Yagra's Sphinx documentation with multilingual support.

## Structure

```
docs/sphinx/
├── source/           # English documentation (primary)
│   ├── conf.py       # Sphinx configuration
│   ├── index.md      # Home page
│   ├── locale/       # Translation files
│   │   ├── *.pot     # Translation templates
│   │   └── ja/       # Japanese translations
│   │       └── LC_MESSAGES/
│   │           └── *.po
│   └── ...
└── _build/
    ├── html/         # English HTML output
    └── html-ja/      # Japanese HTML output
```

## Building Documentation

### English (Primary)

```bash
uv run sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html
```

### Japanese

```bash
uv run sphinx-build -b html -D language=ja docs/sphinx/source docs/sphinx/_build/html-ja
```

## Translating Documentation

### 1. Update POT Files (Translation Templates)

After modifying English source files:

```bash
uv run sphinx-build -b gettext docs/sphinx/source docs/sphinx/source/locale
```

### 2. Update PO Files (Japanese Translations)

```bash
uv run sphinx-intl update -p docs/sphinx/source/locale -l ja -d docs/sphinx/source/locale
```

### 3. Edit PO Files

Open `docs/sphinx/source/locale/ja/LC_MESSAGES/*.po` and fill in translations:

```po
msgid "Getting Started"
msgstr "はじめに"
```

### 4. Build Translated Documentation

```bash
uv run sphinx-build -b html -D language=ja docs/sphinx/source docs/sphinx/_build/html-ja
```

## Translation Guidelines

- **msgid**: Original English text (do not edit)
- **msgstr**: Japanese translation (fill this in)
- Keep Markdown formatting (e.g., `**bold**`, `[link](url)`)
- Keep code blocks and inline code unchanged
- Translate technical terms consistently

## Deployment

GitHub Pages automatically deploys English documentation from `main` branch via `.github/workflows/docs.yml`.

To deploy Japanese version:
1. Update `.github/workflows/docs.yml` to build both languages
2. Add language switcher to Furo theme configuration

## Resources

- [Sphinx i18n Guide](https://www.sphinx-doc.org/en/master/usage/advanced/intl.html)
- [sphinx-intl Documentation](https://sphinx-intl.readthedocs.io/)
- [Furo Theme Documentation](https://pradyunsg.me/furo/)
