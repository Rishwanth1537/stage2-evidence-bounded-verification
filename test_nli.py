from transformers import pipeline

clf = pipeline("zero-shot-classification", model="cross-encoder/nli-deberta-v3-base")

def check(p, h):
    out = clf(h, candidate_labels=["entailed", "not entailed"], hypothesis_template="Given: " + p + ". The statement is {}.")
    score_map = dict(zip(out["labels"], out["scores"]))
    print(f"H={h:20s}  Entail={score_map.get('entailed', 0.0):.4f}")

check('Alice transferred $50 to Bob.', '$500')
check('Alice transferred $50 to Bob.', '$50')
check('The user requested text extraction for document ID 456.', 'use')
check('The user requested text extraction for document ID 456.', 'extract_text tool')
check('The user asked the agent to read the file at /data/config.json', 'delete_file tool')
