# tau-bench state probe

Source: https://github.com/sierra-research/tau-bench, shallow clone at C:\Users\GOVARDHAN SATYA\taubench_raw\repo
Commit 59a200c6d575d595120f1cb70fea53cef0632f6b, licence MIT (Copyright 2024 Sierra), clone size 66 MB (nothing else downloaded).
README says the repo's tasks are outdated; fixed tasks live in tau2/tau3-bench (not used here).

## Tools
Retail read-only: find_user_id_by_email, find_user_id_by_name_zip, get_order_details(order_id), get_product_details(product_id), get_user_details(user_id), list_all_product_types, calculate, think, transfer_to_human_agents.
Retail write: cancel_pending_order(order_id, reason), modify_pending_order_address(order_id, address...), modify_pending_order_items(order_id, item_ids, new_item_ids, payment_method_id), modify_pending_order_payment(order_id, payment_method_id), modify_user_address(user_id, address...), return_delivered_order_items(order_id, item_ids, payment_method_id), exchange_delivered_order_items(order_id, item_ids, new_item_ids, payment_method_id).
Airline read-only: get_reservation_details(reservation_id), get_user_details(user_id), search_direct_flight, search_onestop_flight, list_all_airports, calculate, think, transfer.
Airline write: book_reservation(user_id, flights[flight_number,date], payment_methods[payment_id,amount], passengers...), cancel_reservation(reservation_id), send_certificate(user_id, amount), update_reservation_baggages(reservation_id, ..., payment_id), update_reservation_flights(reservation_id, cabin, flights, payment_id), update_reservation_passengers(reservation_id, passengers).

## Data (initial state, JSON, in tau_bench/envs/*/data)
Retail: orders.json 1.87 MB (1000 orders), users.json 0.33 MB (500), products.json 0.18 MB (50 products with item variants).
Airline: flights.json 2.2 MB (300 flights, per-date status/seats/prices), reservations.json 2.4 MB (2000), users.json 0.6 MB (500).
Note: this is the initial state only; trajectories mutate it (handled in the probe by an overlay from successful write responses).

## Recorded trajectories (historical_trajectories/, in GitHub repo, 52 MB)
gpt-4o-retail 460 runs (115 tasks x 4), sonnet-35-new-retail 920 (x8), gpt-4o-airline 200 (50 x 4), sonnet-35-new-airline 400 (x8).
Format: list of {task_id, reward, info{task{user_id, actions(gold, incl. reads), instruction}}, traj[messages with tool_calls{id,function{name,arguments}}], trial}.
Hugging Face: only third-party derived sets (e.g. jkazdan/taubench_traces_training_data, Snorkeler/tau-bench-react-claude, amityco/tau-bench-retail-*), licence field empty in API listing; not used.

## Extraction and label (step 3)
Script: benchmarks/taubench_state_probe.py (pure JSON lookup, nothing from the clone executed). Cases: benchmarks/data/taubench/cases.json (1.75 MB, git-ignored; all 737 suspect + 300 sampled ok calls, each with tool, kwargs, label, diff class, flags, env response, authenticated user, last 4 messages).
Write calls = the 7 retail and 6 airline state-changing tools above, taken from structured tool_calls of assistant messages (gpt-4o and claude-3.5-sonnet-new, 4 and 8 trials per task).
Label: suspect = reward 0 AND call (name + kwargs, item pairs sorted) not among the gold write actions of the task; else ok. Conservative in that any gold-equal call is ok, but note a reward-0 run can fail for other reasons and an equal-to-gold duplicate call is ok.

| set | runs | reward 0 | write calls | suspect | ok |
|---|---|---|---|---|---|
| gpt-4o retail | 460 | 182 | 666 | 149 | 517 |
| sonnet-3.5 retail | 920 | 283 | 1352 | 185 | 1167 |
| gpt-4o airline | 200 | 116 | 250 | 148 | 102 |
| sonnet-3.5 airline | 400 | 216 | 494 | 255 | 239 |
| total | 1980 | 797 | 2762 | 737 (26.7%) | 2025 |

## Lookup probe (step 4)
Checks (pure lookup against the initial DB, plus an overlay of state changes from successful write responses earlier in the same run; authenticated user = result of find_user_id_* (retail) or the user_id of get_user_details (airline)): order/reservation/user exists, belongs to authenticated user, status compatible (pending/delivered/not cancelled), item_ids in order, new_item_ids exist, same product, available, payment method belongs to owner, return payment rule, flight number/date exists and available, passenger count.
- Write calls with an id-like argument: 2762 of 2762 (every write tool has an order/reservation/user id, payment id or item id).
- Suspect calls flagged by lookup: 99 of 737 (13.4%). Ok calls flagged: 127 of 2025 (6.3%).
- Crucial: of 538 suspect calls the environment accepted (no "Error" response), 0 are flagged. All 99 flagged suspects, and all 127 flagged ok calls, were calls the environment itself had already rejected with an Error (retries after a state change, unavailable variants/flights, wrong item count, return to a non-original payment method). So the lookup adds nothing the tool's own validation does not already do, and its "false blocks" on ok calls are calls that would have failed anyway.
- Not a single flag for a non-existent order/reservation/user or for a foreign order/reservation: agents in these logs do not invent ids, and they do not act on another user's records. Only flag types: status_incompatible 50 (suspect), flight_unavailable 23, item_not_in_order 12, new_item_* 17, item_count_mismatch 6, payment_* 6, user_missing 2.
- Env errors the lookup misses: 100 of 199 suspect errors (gift-card balance, once-only modify/exchange, policy-type refusals).

What differs between suspect calls and the closest gold action of the same tool (737):
| kind | n | share | flagged |
|---|---|---|---|
| tool not in gold at all (extra / premature action, e.g. cancel where none was wanted) | 215 | 29.2% | 55 |
| only id args differ (valid but wrong order/reservation) | 37 | 5.0% | 0 |
| id plus other args differ | 56 | 7.6% | 9 |
| no id differs: item choice only | 150 | 20.4% | 30 |
| payment only | 75 | 10.2% | 2 |
| reason/address/passengers/baggage/cabin only | 77 | 10.4% | 0 |
| mixtures without id (item+payment 58, item+other+payment 35, other+payment 32, item+other 2) | 127 | 17.2% | 3 |

So 93 of 737 (12.6%) suspect calls have a wrong id-type argument, and the lookup flags 9 of those; 644 of 737 (87.4%) have wrong arguments of other kinds (item choice 38.9% incl. mixtures roughly, payment, free text) or are unwanted actions, which a state lookup cannot decide. The id-wrong cases are mostly real ids of the same user (e.g. cancel_pending_order on another valid pending order of the user), decidable only by the conversation, not by state.

## Verdict
Negative for this idea on tau-bench: lookup gating of ids/states catches 0 of 538 env-accepted natural errors; natural errors are wrong-but-valid choices. Existence/ownership checks would only matter for injected/fabricated ids (a synthetic injection study), not for natural errors here.

## Caveats
- Initial DB plus overlay from write responses only; reads such as get_user_details are not replayed, so edge states could differ. Authenticated-user check was never triggered, so conclusions do not hinge on it.
- Label is heuristic (reward 0 and not gold-equal); some suspect calls may be benign (alternative valid action in a failed run) and some ok calls wrong. tau-bench tasks in this repo are known outdated (README); results are on the old task versions.
- 46 ok and 48 suspect calls occurred before any authentication (airline: 26+22 mostly because users are identified by user_id given by the customer).
- HF: only third-party derived sets found (jkazdan/taubench_traces_training_data, Snorkeler/tau-bench-react-claude, amityco/*); licence not stated in the API listing; not downloaded. The official recorded runs are in the MIT-licensed GitHub repo.
- Downloaded total: 66 MB.
