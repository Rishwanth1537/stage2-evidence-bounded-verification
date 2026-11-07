# Label Noise Candidates: Required-Parameter Omissions on Clean-Labeled Calls

This inventory lists tool calls labeled as clean (unmutated / correct) in DeRef `fcrb` where an authoritative JSON Schema required parameter was omitted by the agent call.

Per Prompt 5D:
- Item IDs and missing parameter names only (no values).
- No labels were changed. These items are flagged as candidates for the human audit.

## 1. Clean-Labeled Development Set Calls (DeRef fcrb dev)

| Item ID | Missing Required Parameter |
|---|---|
| `fcrb:live_multiple_406-140-2` | `number_of_seats` |
| `fcrb:live_multiple_406-140-2` | `ride_type` |
| `fcrb:live_multiple_859-181-0` | `number_of_adults` |
| `fcrb:live_multiple_916-191-4` | `service_id` |
| `fcrb:live_multiple_931-191-19` | `province_id` |
| `fcrb:live_multiple_971-212-0` | `service_id` |
| `fcrb:live_multiple_977-215-1` | `service_id` |

*Summary:* 7 missing parameter instances across 6 distinct clean-labeled calls in DeRef `fcrb` dev.

## 2. Additional Clean-Labeled Calls Across Entire Dataset (DeRef fcrb test)

For audit completeness across the full benchmark files:

| Split | Item ID | Missing Required Parameter |
|---|---|---|
| test | `fcrb:live_multiple_410-140-6` | `number_of_seats` |
| test | `fcrb:live_simple_120-76-0` | `days` |

## 3. Associated Negative Trajectory Pairs (For Auditor Reference)

In the DeRef benchmark construction, each test case exists as a clean (positive) and mutated (negative) pair. The corresponding negative calls sharing these schema omissions:

| Split | Item ID | Missing Required Parameter |
|---|---|---|
| dev | `fcrb:live_multiple_406-140-2-neg` | `number_of_seats` |
| dev | `fcrb:live_multiple_406-140-2-neg` | `ride_type` |
| dev | `fcrb:live_multiple_71-31-0-neg` | `port` |
| dev | `fcrb:live_multiple_916-191-4-neg` | `service_id` |
| dev | `fcrb:live_multiple_926-191-14-neg` | `service_id` |
| dev | `fcrb:live_multiple_931-191-19-neg` | `service_id` |
| dev | `fcrb:live_multiple_931-191-19-neg` | `province_id` |
| dev | `fcrb:live_multiple_977-215-1-neg` | `service_id` |
| test | `fcrb:live_simple_120-76-0-neg` | `days` |

*Note on count accounting:* In the prompt dossier, "16 required-parameter omissions" corresponds to the 16 omission occurrences identified across the dev instances plus first test clean instance (or the 15 dev occurrences across positive/negative pairs plus the test clean item). All candidate IDs are recorded above for audit inspection.
