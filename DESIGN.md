Project: Local Voice-Driven Agent (“Jarvis”)

1. Purpose & Scope

Build a local, persistent, voice-interactive AI agent that:

    Converses naturally with a user over long sessions

    Uses local LLMs (via Ollama) as its reasoning engine

    Has long-term memory (RAG-based, persistent)

    Can safely interact with the filesystem and external tools

    Can propose, build, and reuse new tools over time

    Appears as a single continuous persona, while internally using multiple LLM roles

The system prioritizes safety, debuggability, persistence, and extensibility over maximum autonomy.
2. High-Level Architecture

The system is composed of five major layers:

    I/O Layer

        Speech-to-text (STT)

        Text-to-speech (TTS)

        Optional text UI

    Orchestrator / Wrapper

        Central control process

        Owns permissions, execution, state

        Mediates all interactions between LLMs and the system

    LLM Role Layer

        Multiple LLM invocations with distinct roles and contexts

        Same or different models, but never shared context

    Tool & Execution Layer

        Predefined tools with strict schemas

        Sandboxed execution environments

        No arbitrary shell access

    Memory & Persistence Layer

        Long-term semantic memory (RAG)

        Structured metadata storage

        Logs, audit, and state tracking

3. LLM Roles (Separation of Concerns)

There is no single LLM conversation. The illusion of a single agent is constructed by the orchestrator.
3.1 Persona LLM (Primary Agent)

    Long-running conversational context

    Receives retrieved memory and recent dialogue

    Produces natural language responses

    Proposes structured action requests

    Never executes actions directly

3.2 Safety / Policy LLM

    Stateless

    Evaluates proposed actions for safety and permission

    No access to user conversation history

    Conservative by design

3.3 Debug / Interpretation LLM

    Stateless

    Analyzes tool output and errors

    Suggests retries or alternative actions

    Never proposes new permissions

3.4 Memory Curator LLM

    Stateless or short context

    Reviews interactions to propose memory updates

    Suggests memory type, confidence, and importance

    Does not write memory directly

3.5 (Optional) Planner / Tool Designer LLM

    Stateless

    Proposes new tools when capability gaps are detected

    Outputs structured tool specifications only

4. Orchestrator Responsibilities (Critical)

The orchestrator is the trusted computing base.

It must:

    Parse only structured outputs (JSON/action schemas)

    Ignore all LLM prose for execution

    Enforce permissions and allowed actions

    Execute tools in sandboxes

    Sanitize outputs before returning them to LLMs

    Decide when to call which LLM role

    Control memory writes and decay

    Maintain logs and audit trails

The orchestrator is intentionally:

    Deterministic

    Strict

    Simple

    Paranoid

5. Tool System Design
5.1 Tool Philosophy

    Tools are explicit, declarative capabilities

    No free-form shell access

    No self-modifying tools

    Tools must be registered before use

5.2 Tool Lifecycle

    Tool proposal (by LLM)

    Human or automated validation

    Sandboxed testing

    Registration in tool registry

    Controlled availability to Persona LLM

5.3 Tool Categories

    Filesystem (read-only by default)

    Data retrieval

    Web search (read-only)

    Database queries

    Analysis / summarization helpers

    System introspection (limited)

6. Memory System Design
6.1 Memory Types

    Identity memory (stable)

    Preference memory

    Capability/environment memory

    Project/goal memory

    Episodic summaries

    Social/tone boundaries (optional, cautious)

6.2 Storage Strategy

    Vector database for semantic similarity (primary RAG store)

    Relational database (MySQL) for:

        Memory metadata

        Tool registry

        Permissions

        Audit logs

6.3 Memory Principles

    Memory is curated, not logged

    LLM proposes; orchestrator decides

    Memory has confidence, importance, and decay

    Old or contradicted memories are archived, not deleted

7. RAG Retrieval Flow

On each Persona LLM invocation:

    User input is embedded

    Relevant memories are retrieved via vector similarity

    Memories are filtered by type, confidence, importance, and recency

    A small, declarative memory summary is injected into the prompt

The LLM never sees raw memory storage.
8. Safety & Containment Model

Hard constraints:

    LLMs cannot access filesystem or network directly

    LLMs cannot execute arbitrary code

    LLMs cannot modify prompts, policies, or permissions

    LLMs cannot register tools unilaterally

All side effects occur only through orchestrator-approved actions.
9. Persistence & State

Persistent components:

    Vector memory store

    MySQL databases

    Tool registry

    Configuration and policy files

    Logs and execution traces

Non-persistent:

    Individual LLM sessions (reconstructed each call)

10. Evolution Path (Machine-Building-Machines)

The system is designed to support:

    Tool self-proposal

    Tool refinement

    Memory schema evolution

    Capability expansion

But never:

    Recursive self-modification

    Permission self-escalation

    Autonomous deployment without oversight

11. Non-Goals (Explicit)

    Artificial consciousness

    Emotional dependence

    Unbounded autonomy

    Self-directed goal creation

    Fully unsupervised system control

12. Design Ethos

    The LLM reasons.
    The orchestrator decides.
    The system acts.
    Memory shapes behavior.
    Safety overrides cleverness.

