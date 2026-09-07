<p align="center">
  <img src="https://img.shields.io/badge/SWARMFORGE-AGENT%20ORCHESTRATOR-00E5FF?style=flat-square&labelColor=0a0e1a" alt="swarmforge" />
</p>

# SWARMFORGE :: MULTI-AGENT ORCHESTRATOR

**Design, deploy, and monitor collaborative multi-agent AI workflows.** YAML-defined agent pipelines with shared memory and typed message channels — run with a single command.

<p align="center">
  <img src="https://img.shields.io/badge/PYTHON-%3E%3D3.11-ffc430?style=flat-square&logo=python&logoColor=ffc430&labelColor=0a0e1a" alt="python"/>
  <img src="https://img.shields.io/badge/DEFS-YAML-B8FF1E?style=flat-square&labelColor=0a0e1a" alt="yaml"/>
  <img src="https://img.shields.io/badge/CHANNELS-TYPED-3dd5ff?style=flat-square&labelColor=0a0e1a" alt="channels"/>
  <img src="https://img.shields.io/badge/MEMORY-SHARED-00E5FF?style=flat-square&labelColor=0a0e1a" alt="memory"/>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-ff3b3b?style=flat-square&labelColor=0a0e1a" alt="license"/></a>
</p>

<pre>
IDENT ......... SWARM-01
CLASS ......... MULTI-AGENT ORCHESTRATOR
STATUS ........ ONLINE / ACTIVE
DEFS .......... YAML WORKFLOWS
CHANNELS ...... LLM · TOOL · ROUTER · AGGREGATE
LINK .......... /swarmforge
</pre>

---

## // 01 :: SIGNAL

**SwarmForge** is a multi-agent AI orchestrator that lets you define agent workflows in YAML and run them with a single command. Agents share memory, communicate through typed message channels, and collaborate to solve complex tasks.

No SaaS. No vendor lock-in. Just agents working together.

---

## Features

### Agent types

| Type | Purpose |
|---|---|
| `llm` | LLM-powered agent (any OpenAI-compatible API) |
| `tool` | Executes registered functions/tools |
| `router` | Routes messages based on conditions |
| `aggregate` | Collects and merges outputs from multiple agents |

### Shared memory

All agents read from and write to a shared key-value store. Data flows automatically between steps without manual plumbing.

### Message channels

Typed channels for agent-to-agent communication. Agents can subscribe to channels and react to messages in real-time.

### YAML workflows

Define your entire agent pipeline in a single YAML file — agents, steps, variables, channels, and conditions.

---

## Quick start

```bash
# Install
pip install -e .

# Set your API key
export OPENAI_API_KEY=sk-...

# Run an example workflow
swarmforge run examples/research-workflow.yaml

# Validate a workflow
swarmforge validate my-workflow.yaml
```

---

## Workflow format

```yaml
name: my-pipeline
description: A multi-agent research pipeline

variables:
  topic: "quantum computing"

agents:
  - name: researcher
    type: llm
    model: gpt-4o
    system_prompt: "You are a research agent."

  - name: writer
    type: llm
    model: gpt-4o
    system_prompt: "You are a technical writer."

steps:
  - name: research
    agent: researcher
    input:
      task: "Research: {{topic}}"
    output: research_result

  - name: write
    agent: writer
    input:
      task: "Write a report based on:"
      data: "{{research_result}}"
    output: final_report

channels:
  - name: research-feed
    source: researcher
    target: writer
```

---

## How it works

```
Workflow YAML
      │
      ▼
┌─────────────┐
│ SwarmEngine │
├─────────────┤
│  Agents     │ ◄── LLM / Tool / Router / Aggregate
│  Memory     │ ◄── Shared key-value store
│  Bus        │ ◄── Typed message channels
└──────┬──────┘
       │
       ▼
  Step-by-step execution with shared state
```

---

## Requirements

- Python 3.11+
- OpenAI API key (or any OpenAI-compatible endpoint)
- `requests`, `rich`, `pyyaml`

---

## License

[MIT](LICENSE) — PlayNexus
