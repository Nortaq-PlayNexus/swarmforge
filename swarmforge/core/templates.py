"""Pre-built workflow templates for SwarmForge."""

from __future__ import annotations
from typing import Any


RESEARCH_TEMPLATE: dict[str, Any] = {
    "name": "research-pipeline",
    "description": "Multi-agent research workflow: search, analyze, and summarize findings.",
    "agents": [
        {
            "name": "searcher",
            "type": "llm",
            "system_prompt": "You are a research search agent. Find relevant information on the given topic.",
        },
        {
            "name": "analyzer",
            "type": "llm",
            "system_prompt": "You are a research analysis agent. Analyze the provided research data and extract key insights.",
        },
        {
            "name": "summarizer",
            "type": "llm",
            "system_prompt": "You are a research summarizer. Produce a clear, concise summary from the analyzed findings.",
        },
    ],
    "steps": [
        {
            "name": "search",
            "agent": "searcher",
            "input": {"topic": "var.topic"},
            "output": "search_results",
        },
        {
            "name": "analyze",
            "agent": "analyzer",
            "input": {"research_data": "search_results"},
            "output": "analysis",
            "depends_on": ["search"],
        },
        {
            "name": "summarize",
            "agent": "summarizer",
            "input": {"analysis": "analysis"},
            "output": "summary",
            "depends_on": ["analyze"],
        },
    ],
    "variables": {"topic": ""},
}

DATA_PIPELINE_TEMPLATE: dict[str, Any] = {
    "name": "data-pipeline",
    "description": "Data processing pipeline: extract, transform, validate, and load.",
    "agents": [
        {
            "name": "extractor",
            "type": "tool",
            "config": {"description": "Extracts data from source systems."},
        },
        {
            "name": "transformer",
            "type": "python",
            "config": {"allowed_modules": ["json", "math", "re"]},
        },
        {
            "name": "validator",
            "type": "llm",
            "system_prompt": "You are a data validation agent. Validate the transformed data against expected schemas.",
        },
        {
            "name": "loader",
            "type": "tool",
            "config": {"description": "Loads validated data into target systems."},
        },
    ],
    "steps": [
        {
            "name": "extract",
            "agent": "extractor",
            "input": {"source": "var.source"},
            "output": "raw_data",
        },
        {
            "name": "transform",
            "agent": "transformer",
            "input": {"code": "var.transform_code", "raw_data": "raw_data"},
            "output": "transformed_data",
            "depends_on": ["extract"],
        },
        {
            "name": "validate",
            "agent": "validator",
            "input": {"data": "transformed_data", "schema": "var.schema"},
            "output": "validated_data",
            "depends_on": ["transform"],
            "retry_count": 2,
            "retry_backoff": 1.0,
        },
        {
            "name": "load",
            "agent": "loader",
            "input": {"tool": "write", "args": {"data": "validated_data"}},
            "output": "load_result",
            "depends_on": ["validate"],
            "on_failure": "retry",
        },
    ],
    "variables": {
        "source": "",
        "transform_code": "result['output'] = input_data.get('raw_data', '')",
        "schema": "{}",
    },
}

CODE_REVIEW_TEMPLATE: dict[str, Any] = {
    "name": "code-review",
    "description": "Code review workflow: analyze, review, suggest fixes, and aggregate feedback.",
    "agents": [
        {
            "name": "analyzer",
            "type": "llm",
            "system_prompt": "You are a code analysis agent. Analyze the provided code for structure, complexity, and potential issues.",
        },
        {
            "name": "reviewer",
            "type": "llm",
            "system_prompt": "You are a code review agent. Perform a thorough code review focusing on correctness, security, and best practices.",
        },
        {
            "name": "suggester",
            "type": "llm",
            "system_prompt": "You are a code suggestion agent. Provide concrete code suggestions and fixes for identified issues.",
        },
        {
            "name": "aggregator",
            "type": "aggregate",
        },
    ],
    "steps": [
        {
            "name": "analyze",
            "agent": "analyzer",
            "input": {"code": "var.code"},
            "output": "analysis",
        },
        {
            "name": "review",
            "agent": "reviewer",
            "input": {"code": "var.code", "analysis": "analysis"},
            "output": "review",
            "depends_on": ["analyze"],
        },
        {
            "name": "suggest",
            "agent": "suggester",
            "input": {"code": "var.code", "review": "review"},
            "output": "suggestions",
            "depends_on": ["review"],
        },
        {
            "name": "aggregate",
            "agent": "aggregator",
            "input": {"sources": ["analysis", "review", "suggestions"]},
            "output": "final_report",
            "depends_on": ["suggest"],
        },
    ],
    "variables": {"code": ""},
}

CUSTOMER_SUPPORT_TEMPLATE: dict[str, Any] = {
    "name": "customer-support",
    "description": "Customer support workflow: classify, route, respond, and follow up.",
    "agents": [
        {
            "name": "classifier",
            "type": "conditional",
            "config": {
                "match_field": "message",
                "match_type": "contains",
                "routes": {
                    "billing": "billing_agent",
                    "technical": "tech_agent",
                    "general": "general_agent",
                    "default": "general_agent",
                },
            },
        },
        {
            "name": "billing_agent",
            "type": "llm",
            "system_prompt": "You are a billing support specialist. Help customers with billing inquiries.",
        },
        {
            "name": "tech_agent",
            "type": "llm",
            "system_prompt": "You are a technical support specialist. Help customers with technical issues.",
        },
        {
            "name": "general_agent",
            "type": "llm",
            "system_prompt": "You are a general support agent. Help customers with general inquiries.",
        },
        {
            "name": "follow_up",
            "type": "llm",
            "system_prompt": "You are a follow-up agent. Draft a follow-up message to ensure customer satisfaction.",
        },
    ],
    "steps": [
        {
            "name": "classify",
            "agent": "classifier",
            "input": {"message": "var.message"},
            "output": "classification",
        },
        {
            "name": "respond",
            "agent": "general_agent",
            "input": {"message": "var.message"},
            "output": "response",
            "depends_on": ["classify"],
            "on_failure": "fallback",
        },
        {
            "name": "follow_up",
            "agent": "follow_up",
            "input": {"message": "var.message", "response": "response"},
            "output": "follow_up_message",
            "depends_on": ["respond"],
            "on_failure": "skip",
        },
    ],
    "variables": {"message": ""},
}

ALL_TEMPLATES: dict[str, dict[str, Any]] = {
    "research": RESEARCH_TEMPLATE,
    "data-pipeline": DATA_PIPELINE_TEMPLATE,
    "code-review": CODE_REVIEW_TEMPLATE,
    "customer-support": CUSTOMER_SUPPORT_TEMPLATE,
}
