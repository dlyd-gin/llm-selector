# LLM Selector Documentation

This directory contains additional documentation resources for the llm-selector library.

## Documentation Structure

### Main Documentation Files (in parent directory)

- **[WORKFLOW_DIAGRAMS.md](../WORKFLOW_DIAGRAMS.md)** - Comprehensive workflow diagrams
  - High-level architecture
  - Random selection workflows (happy/unhappy scenarios)
  - Round-robin selection workflows (complex scenarios)
  - Detailed algorithm flowcharts
  - State management diagrams
  - Error handling flows
  - Usage patterns

- **[README.md](../README.md)** - Main library documentation
  - Quick start guide
  - API reference
  - Configuration
  - Troubleshooting

- **[BEHAVIOR_COMPARISON.md](../BEHAVIOR_COMPARISON.md)** - Random vs round-robin comparison

- **[IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)** - Quick implementation reference

## Diagram Formats

All diagrams use **Mermaid** syntax, which renders automatically on:
- GitHub
- GitLab
- VS Code (with Markdown Preview Mermaid Support extension)
- Many documentation platforms

### Viewing Diagrams

**In GitHub/GitLab:**
- Diagrams render automatically when viewing markdown files

**In VS Code:**
1. Install "Markdown Preview Mermaid Support" extension
2. Open any .md file
3. Click "Preview" button (Ctrl+Shift+V)

**Online:**
- Use [Mermaid Live Editor](https://mermaid.live/)
- Copy diagram code and paste for rendering

### Exporting Diagrams as Images

If you need PNG/SVG exports for presentations:

**Option 1: Mermaid CLI**
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i diagram.mmd -o diagram.png
```

**Option 2: Online Editor**
1. Open [Mermaid Live Editor](https://mermaid.live/)
2. Paste diagram code
3. Use export button for PNG/SVG

**Option 3: Screenshots**
- View rendered markdown in GitHub
- Take screenshots of individual diagrams

## Using This Documentation

### For Understanding the Library

1. Start with [README.md](../README.md) for basic usage
2. Review [WORKFLOW_DIAGRAMS.md](../WORKFLOW_DIAGRAMS.md) to understand:
   - How components interact
   - Selection strategies
   - Failure handling
3. Check [BEHAVIOR_COMPARISON.md](../BEHAVIOR_COMPARISON.md) to choose strategy

### For Knowledge Transfer

Use the documentation in this order:

1. **High-level overview**: [README.md](../README.md) - Features and basic usage
2. **Visual understanding**: [WORKFLOW_DIAGRAMS.md](../WORKFLOW_DIAGRAMS.md) - Architecture and flows
3. **Strategy comparison**: [BEHAVIOR_COMPARISON.md](../BEHAVIOR_COMPARISON.md) - When to use what
5. **Quick reference**: [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Key points

## Key Concepts

### Selection Strategies

**Random Selection** (`as_equal_as_possible=False`)
- Default behavior
- Uses `random.choice()` from available providers
- Simple and effective
- No state tracking for selection order

**Round-Robin Selection** (`as_equal_as_possible=True`)
- Equal distribution guarantee
- Tracks last used provider by ID (not index)
- Maintains sequence even with failures
- Best for fair load balancing

### Cooldown Logic

- **Duration**: 60 seconds
- **Trigger**: Any failure (429, 5xx)
- **Behavior**: Provider filtered from available list
- **Expiry**: Automatic after 60 seconds
- **Update**: Only if new failure occurs >60s after previous

### Round-Robin Algorithm

Key insight: **Tracks by provider ID, not index**

Why this matters:
- Providers can go in/out of cooldown
- Configuration order is maintained
- Sequence never skips providers
- Handles failures gracefully

Example:
```
Config: [A, B, C, D]
Last used: B
Available: [A, C, D] (B in cooldown)

Next provider: C (not A!)
Because sequence is: A → B → C → D, and last used was B
```

## Contributing to Documentation

When adding or updating documentation:

1. **Keep diagrams simple** - Split complex flows into multiple diagrams
2. **Use Mermaid** - Text-based, version-controllable
3. **Add examples** - Use actual provider names from config
4. **Explain "why"** - Not just "what"
5. **Include edge cases** - Show unhappy paths
6. **Test rendering** - View in GitHub preview before committing

## Support

For issues or questions about the documentation:
- Open an issue on the project repository
- Include the specific document and section
- Suggest improvements

## Version History

- **v1.0** - Initial comprehensive documentation
  - Workflow diagrams with Mermaid
  - Updated README with links
  - Docs directory structure
