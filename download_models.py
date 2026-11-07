import subprocess
import sys

def main():
    print("Downloading spaCy model (en_core_web_trf)...")
    try:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_trf"])
    except subprocess.CalledProcessError as e:
        print(f"Error downloading spaCy model: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nDownloading HuggingFace models...")
    try:
        from transformers import pipeline
        
        print(" -> Downloading dslim/bert-base-NER...")
        pipeline("ner", model="dslim/bert-base-NER")
        
        print(" -> Downloading cross-encoder/nli-deberta-v3-base...")
        pipeline("zero-shot-classification", model="cross-encoder/nli-deberta-v3-base")
        
    except ImportError:
        print("Error: transformers is not installed. Please install requirements first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error downloading HuggingFace models: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nAll required models downloaded successfully!")

if __name__ == "__main__":
    main()
