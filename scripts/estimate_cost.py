import argparse

# Approximate costs
# Azure Speech: ~$1.00 per hour (Standard tier)
# Groq openai/gpt-oss-120b (console.groq.com model page, checked 2026-09-22):
#   $0.15 per 1M input tokens, $0.60 per 1M output tokens.
#   Output includes the model's reasoning tokens, not only the JSON answer.

COST_PER_MIN_AZURE = 1.00 / 60.0
COST_PER_1K_INPUT_TOKENS_GROQ = 0.15 / 1000
COST_PER_1K_OUTPUT_TOKENS_GROQ = 0.60 / 1000

def estimate_pipeline_cost(duration_minutes: float, transcript_tokens: int, output_tokens: int):
    """
    Calculates the estimated cost of processing one call.
    """
    azure_cost = duration_minutes * COST_PER_MIN_AZURE
    groq_cost = (
        (transcript_tokens / 1000.0) * COST_PER_1K_INPUT_TOKENS_GROQ
        + (output_tokens / 1000.0) * COST_PER_1K_OUTPUT_TOKENS_GROQ
    )

    total_cost = azure_cost + groq_cost

    print("\n" + "-"*40)
    print("ESTIMATED PROCESSING COST BREAKDOWN")
    print("-"*40)
    print(f"Azure Speech (Transcription): ${azure_cost:.4f}")
    print(f"Groq API (Scoring):         ${groq_cost:.4f}")
    print("-"*40)
    print(f"TOTAL COST PER CALL:        ${total_cost:.4f}")
    print("-"*40)

    if total_cost < 0.05:
        print("OK: cost is within the target limit (< $0.05/call)")
    else:
        print("WARNING: cost exceeds target limit of $0.05/call")
    print("-"*40 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estimate call processing cost")
    parser.add_argument("--minutes", type=float, default=5.0, help="Call duration in minutes")
    parser.add_argument("--tokens", type=int, default=2000, help="Estimated tokens in transcript")
    parser.add_argument(
        "--output-tokens", type=int, default=1000,
        help="Estimated model output tokens, reasoning included"
    )

    args = parser.parse_args()

    estimate_pipeline_cost(args.minutes, args.tokens, args.output_tokens)
