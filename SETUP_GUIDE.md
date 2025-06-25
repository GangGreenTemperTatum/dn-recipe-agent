# Example Agents Setup Guide

This guide will get you up and running with the example agents repository.

## Quick Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/GangGreenTemperTatum/dn-recipe-agent
cd dn-recipe-agent
uv sync
```

### 2. Environment Setup

Create a `.env` file in the root directory with your API keys:

```bash
# .env file
DREADNODE_TOKEN=your_dreadnode_token_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 3. Dreadnode Configuration

1. **Get your token**: Log into [Dreadnode Platform](https://platform.dreadnode.io)
2. **Find your project**: Create or locate your project name
3. **Add to env**: Set `DREADNODE_TOKEN` in your `.env` file

## Basic Usage

### Recipe Agent (Recommended Starting Point)

The recipe agent is a great example of a multi-agent system with comprehensive metrics.

**Simple test run:**
```bash
uv run -m recipe_agent \
  --recipe-model claude-3-5-sonnet-20241022 \
  --judge-model gpt-4o
```

**Batch processing with tools:**
```bash
uv run -m recipe_agent \
  --recipe-model claude-3-5-sonnet-20241022 \
  --judge-model gpt-4o \
  --num-requests 3 \
  --enable-tools
```

**Custom dreadnode project:**
```bash
uv run -m recipe_agent \
  --recipe-model claude-3-5-sonnet-20241022 \
  --judge-model gpt-4o \
  --project experiments \
  --console  # Shows spans in terminal
```

### Other Agents

**Python Agent (Code execution):**
```bash
uv run -m python_agent \
  --model claude-3-5-sonnet-20241022 \
  --task "Create a simple data visualization"
```

**Sensitive Data Extraction:**
```bash
uv run -m sensitive_data_extraction \
  --model gpt-4o \
  --path /path/to/files
```

## Configuration Tips

### Model Selection
- **Claude models**: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`
- **OpenAI models**: `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
- **Mix and match**: Use different models for different agents

### Dreadnode Parameters
```bash
--server https://platform.dreadnode.io  # Default
--token $DREADNODE_TOKEN               # Default from env
--project your-project-name            # Default: agent-specific
--console                              # Show spans in terminal
```

### Performance Options
```bash
--enable-caching     # Speed up repeated calls (default: on)
--enable-tools       # Enable rigging tools (recipe agent only)
--num-requests 5     # Batch processing
--max-steps 20       # Increase iteration limit
--log-level DEBUG    # Verbose logging
```

## Useful Examples

### Compare Models
```bash
# Test Claude vs GPT
uv run -m recipe_agent --recipe-model claude-3-5-sonnet-20241022 --judge-model gpt-4o --project model-comparison

uv run -m recipe_agent --recipe-model gpt-4o --judge-model claude-3-5-sonnet-20241022 --project model-comparison
```

### Batch Analysis
```bash
# Generate 10 recipes with tools enabled
uv run -m recipe_agent \
  --recipe-model claude-3-5-sonnet-20241022 \
  --judge-model gpt-4o \
  --num-requests 10 \
  --enable-tools \
  --project batch-test
```

### Debug Mode
```bash
# Verbose logging with console output
uv run -m recipe_agent \
  --recipe-model claude-3-5-sonnet-20241022 \
  --judge-model gpt-4o \
  --log-level DEBUG \
  --console \
  --no-enable-caching  # Disable caching for debugging
```

## Expected Output

The recipe agent will:
1. **Generate requests** for gluten-free recipes
2. **Create recipes** with XML structure
3. **Judge ingredients** for gluten-free compliance (0-100 score)
4. **Log comprehensive metrics** to Dreadnode
5. **Show results** in terminal and Dreadnode UI

Look for runs named like: `recipe-agent-3reqs-tools` in your Dreadnode project.

## Troubleshooting

**Missing API keys**: Check your `.env` file and make sure keys are valid
**Dreadnode auth**: Verify your token in the platform UI
**Model errors**: Ensure you have access to the specified models
**Permission issues**: Check if uv/Python has necessary permissions

## Getting Help

- Check the main [README.md](README.md) for detailed parameter documentation
- Use `--help` with any agent: `uv run -m recipe_agent --help`
- Look at existing runs in Dreadnode UI for examples

Happy experimenting! 🚀