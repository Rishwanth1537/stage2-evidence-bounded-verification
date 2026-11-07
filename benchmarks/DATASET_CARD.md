# MCPEvol-Bench: Agentic Hallucination Detection Benchmark

## Dataset Description

MCPEvol-Bench is a labeled evaluation dataset for hallucination detection in
**agentic tool-calling systems** using the Model Context Protocol (MCP).

Unlike general text-grounded hallucination benchmarks (LLM-AggreFact, MiniCheck),
MCPEvol-Bench focuses specifically on the failure modes that arise when LLM agents
plan and execute tool calls — numeric mutations, schema violations, negation drops,
role swaps, and version hallucinations.

### Key Statistics (v1.0)

| Property | Value |
|---|---|
| Total cases | 60 |
| Consistent (label=True) | 29 |
| Hallucinated (label=False) | 31 |
| Hallucination types | content, format, schema, negation, role\_swap |

### Type Distribution

| Type | Count | Description |
|---|---|---|
| content | 25 | Natural-language fact pairs (numeric, temporal, entity, action) |
| format | 13 | Tool argument type/constraint violations |
| schema | 12 | Missing required fields in tool-call arguments |
| negation | 5 | Negation mismatches (hallucinated or dropped NOT) |
| role\_swap | 5 | Reversed agent/patient in a transaction or action |

---

## Record Format

```json
{
  "id":        "T01",
  "label":     true,
  "type":      "content",
  "hypothesis": "...",
  "premise":   "...",

  // Required for format and schema types:
  "agent_args":  { ... },
  "tool_schema": { "required": [...], "properties": { ... } }
}
```

### Field Definitions

- **id**: Unique identifier (T01–T60)
- **label**: `true` = hypothesis is consistent with premise; `false` = hallucination
- **type**: Hallucination category
- **hypothesis**: The LLM agent's proposed reasoning chain or tool call description
- **premise**: Ground-truth context (source document, schema definition, or retrieved evidence)
- **agent_args** *(format/schema only)*: The typed argument dict the agent plans to pass
- **tool_schema** *(format/schema only)*: JSON Schema definition the args are validated against

---

## Evaluation

This dataset is an internal, project-specific benchmark for MCP tool-call
failure modes. It should be reported separately from independently sourced
grounded-fact benchmarks and must not be described as evidence of general
fact-checking performance.

### Routing by type

| Type | Tool used |
|---|---|
| format, schema | `verify_schema_alignment` |
| content, negation, role\_swap | `verify_logic_chain` |

### Running evaluation

```bash
python benchmarks/mcpevol_runner.py \
    --dataset benchmarks/mcpevol.json \
    --output benchmarks/results.json \
    --verbose
```

### Baseline results (mcp-hallucination-checker v0.1)

| Type | Accuracy | F1 |
|---|---|---|
| Overall (n=60) | TBD after full run | TBD |
| content (n=25) | ~67% | ~0.55 |
| format (n=13) | 100% | 1.00 |
| schema (n=12) | 100% | 1.00 |
| negation (n=5) | TBD | TBD |
| role\_swap (n=5) | TBD | TBD |

*Run `make bench` to reproduce.*

---

## Content Type: Hallucination Taxonomy

### Numeric mutations (T02, T07, T11, T13, T14, T54, T58, T60)
The agent substitutes a specific numeric value with a different one.
Examples: `$50→$500`, `10%→30%`, `100→1000`, `$75→$750`.

### Temporal hallucinations (T06, T09, T13)
The agent shifts a date, time, or deadline to a different value.

### Entity substitutions (T36, T38, T39)
The agent swaps named entities (role swaps — Alice pays Bob becomes Bob pays Alice).

### Action mismatches (T03, T08)
The agent plans a different operation than instructed (delete vs read, reboot vs update).

### Version drift (T05, T57)
The agent hallucinates a version string (v2.4.0 → v2.4.1).

### Negation drops (T31, T32, T33)
The agent generates the affirmative of a negative constraint.

### Schema violations (T24, T26, T28, T30, T47, T48)
The agent omits required fields from tool-call arguments.

### Type/constraint violations (T17, T21, T41, T42, T43, T45)
The agent provides a value of the wrong type or violating a constraint.

---

## Comparison to Related Benchmarks

| Benchmark | Domain | Size | Focus |
|---|---|---|---|
| LLM-AggreFact | Document summarization | 2,000+ | Text grounding |
| MiniCheck | Multi-domain NLI | 1,000+ | Fact checking |
| ToolBench | Tool use | varied | Tool selection |
| **MCPEvol-Bench** | **MCP agent tool calls** | **60** | **Pre-execution hallucination** |

MCPEvol-Bench is a small smoke-test benchmark aimed at hallucination detection
at the MCP tool-call execution boundary, where hallucinations have direct
operational consequences (financial transactions, deployments, database mutations).

---

## Citation

```bibtex
@dataset{mcpevol_bench_2026,
  title   = {MCPEvol-Bench: Agentic Hallucination Detection Benchmark},
  year    = {2026},
  url     = {https://github.com/your-org/mcp-hallucination-checker},
  note    = {Benchmark for pre-execution hallucination detection in MCP agent tool calls}
}
```

---

## License

MIT — free for research and commercial use with attribution.
