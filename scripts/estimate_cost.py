import argparse

# Updated approximate costs as of 2026
# Azure Speech: ~$1.00 per hour (Standard tier)
# Groq: Llama 3.3 70B is very cost-efficient, approx $0.60 per 1M tokens

COST_PER_MIN_AZURE = 1.00 / 60.0
COST_PER_1K_TOKENS_GROQ = 0.0006  # $0.60 / 1000

def estimate_pipeline_cost(duration_minutes: float, transcript_tokens: int):
    """
    Calculates the estimated cost of processing one call.
    """
    azure_cost = duration_minutes * COST_PER_MIN_AZURE
    groq_cost = (transcript_tokens / 1000.0) * COST_PER_1K_TOKENS_GROQ
    
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
        print("✅ Cost is within the target limit (< $0.05/call)")
    else:
        print("⚠️ Cost exceeds target limit of $0.05/call")
    print("-"*40 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estimate call processing cost")
    parser.add_argument("--minutes", type=float, default=5.0, help="Call duration in minutes")
    parser.add_argument("--tokens", type=int, default=2000, help="Estimated tokens in transcript")
    
    args = parser.parse_args()
    
    estimate_pipeline_cost(args.minutes, args.tokens)
