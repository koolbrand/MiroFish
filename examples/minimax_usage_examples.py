"""
MiniMax M2.7 Integration Examples for MiroFish

These examples demonstrate how to use MiniMax M2.7 in different scenarios within MiroFish.
"""

import os
from typing import List, Dict
from openai import OpenAI

# Initialize with MiniMax Token Plan API Key
def get_minimax_client():
    """Initialize MiniMax client with Token Plan API key"""
    return OpenAI(
        api_key=os.environ.get('LLM_API_KEY'),
        base_url=os.environ.get('LLM_BASE_URL', 'https://api.minimax.io/v1')
    )


# ============================================================================
# Example 1: Simple Chat Completion
# ============================================================================

def example_simple_chat():
    """Simple chat completion with MiniMax M2.7"""
    client = get_minimax_client()

    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant analyzing swarm intelligence patterns."
            },
            {
                "role": "user",
                "content": "What are the key factors for effective swarm collaboration?"
            }
        ],
        temperature=0.7,
        max_tokens=1024
    )

    print("Response:", response.choices[0].message.content)
    return response


# ============================================================================
# Example 2: Multi-turn Conversation
# ============================================================================

def example_multi_turn_conversation():
    """Multi-turn conversation with context preservation"""
    client = get_minimax_client()

    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": "You are an AI agent designer for MiroFish simulation."
        }
    ]

    # First turn
    messages.append({
        "role": "user",
        "content": "Design a simple trading agent for a market simulation."
    })

    response1 = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=messages,
        temperature=0.7,
        max_tokens=2048
    )

    agent_design = response1.choices[0].message.content
    print("Agent Design:\n", agent_design)

    # Important: Append the full assistant message for reasoning chain continuity
    messages.append({
        "role": "assistant",
        "content": agent_design
    })

    # Second turn - follow up
    messages.append({
        "role": "user",
        "content": "What behavioral rules should this agent follow?"
    })

    response2 = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=messages,
        temperature=0.7,
        max_tokens=2048
    )

    behavioral_rules = response2.choices[0].message.content
    print("\nBehavioral Rules:\n", behavioral_rules)

    return messages


# ============================================================================
# Example 3: Streaming Response (Real-time Output)
# ============================================================================

def example_streaming_response():
    """Stream response for real-time output"""
    client = get_minimax_client()

    print("Streaming response:\n")

    stream = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=[
            {
                "role": "user",
                "content": "Describe the 5 key features of MiniMax M2.7 for agent programming."
            }
        ],
        stream=True,
        temperature=0.7,
        max_tokens=1024
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    print()  # New line after streaming


# ============================================================================
# Example 4: JSON Response Format
# ============================================================================

def example_json_response():
    """Get structured JSON response"""
    client = get_minimax_client()

    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=[
            {
                "role": "user",
                "content": """Generate a JSON structure for a social media agent profile.

Required fields:
- agent_id: unique identifier
- personality_traits: list of traits
- decision_making_style: how the agent makes decisions
- risk_tolerance: risk preference (low/medium/high)

Return only valid JSON."""
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1024
    )

    import json
    content = response.choices[0].message.content
    # Clean markdown code blocks if present
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    agent_profile = json.loads(content.strip())
    print("Agent Profile:", json.dumps(agent_profile, indent=2))
    return agent_profile


# ============================================================================
# Example 5: Using Interleaved Thinking (M2.7 Feature)
# ============================================================================

def example_thinking_process():
    """Access M2.7's thinking process for complex reasoning"""
    client = get_minimax_client()

    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=[
            {
                "role": "user",
                "content": """Analyze this agent interaction scenario and predict outcomes:

A social media agent with high engagement tendency meets a content moderation rule.
The agent is currently at 80% opinion strength.
What's the probability it follows the rule vs ignores it?
Provide detailed reasoning."""
            }
        ],
        # Separate thinking content into reasoning_details field
        extra_body={"reasoning_split": True},
        temperature=0.7,
        max_tokens=2048
    )

    # Access thinking content
    if hasattr(response.choices[0].message, 'reasoning_details'):
        thinking = response.choices[0].message.reasoning_details
        print("🧠 Model Thinking Process:")
        for detail in thinking:
            if 'text' in detail:
                print(detail['text'])
        print("\n")

    content = response.choices[0].message.content
    print("📊 Analysis Result:")
    print(content)

    return response


# ============================================================================
# Example 6: Token Counting (Estimation)
# ============================================================================

def example_estimate_tokens(text: str) -> int:
    """Rough token estimation (actual counting requires additional setup)"""
    # Rough estimation: ~1 token per 4 characters for English
    # MiniMax uses similar tokenization to OpenAI
    estimated_tokens = len(text) // 4
    print(f"Text length: {len(text)} chars")
    print(f"Estimated tokens: ~{estimated_tokens}")
    return estimated_tokens


# ============================================================================
# Example 7: Error Handling
# ============================================================================

def example_error_handling():
    """Proper error handling for API calls"""
    client = get_minimax_client()

    try:
        response = client.chat.completions.create(
            model="MiniMax-M2.7",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            temperature=0.5,
            max_tokens=100
        )
        print("Success:", response.choices[0].message.content)

    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")

        # Handle specific errors
        if "api_key" in str(e).lower():
            print("❌ API Key issue - check LLM_API_KEY")
        elif "model" in str(e).lower():
            print("❌ Model not found - check LLM_MODEL_NAME")
        elif "base_url" in str(e).lower():
            print("❌ Invalid endpoint - check LLM_BASE_URL")


# ============================================================================
# Example 8: Performance Optimization
# ============================================================================

def example_highspeed_model():
    """Use M2.7-highspeed for better throughput (~100 tps)"""
    client = get_minimax_client()

    response = client.chat.completions.create(
        model="MiniMax-M2.7-highspeed",  # Faster variant
        messages=[
            {"role": "user", "content": "Quick response needed!"}
        ],
        temperature=0.7,
        max_tokens=512
    )

    print("Fast response:", response.choices[0].message.content)
    return response


# ============================================================================
# Example 9: Integration with MiroFish LLMClient
# ============================================================================

def example_mirofish_integration():
    """Example of using MiniMax with MiroFish's LLMClient wrapper"""
    from backend.app.utils.llm_client import LLMClient

    # Initialize with default config from .env
    llm_client = LLMClient()

    # Use chat method
    response = llm_client.chat(
        messages=[
            {"role": "user", "content": "What is swarm intelligence?"}
        ],
        temperature=0.7,
        max_tokens=1024
    )

    print("MiroFish LLMClient response:", response)

    # Use chat_json for structured output
    json_response = llm_client.chat_json(
        messages=[
            {
                "role": "user",
                "content": """Return JSON with:
                - title: "Swarm Intelligence"
                - description: brief description
                - applications: list of applications"""
            }
        ],
        temperature=0.3
    )

    print("Structured response:", json_response)
    return response


# ============================================================================
# Main Function - Run Examples
# ============================================================================

if __name__ == "__main__":
    import dotenv

    # Load environment variables from .env
    dotenv.load_dotenv()

    print("=" * 70)
    print("MiniMax M2.7 Integration Examples for MiroFish")
    print("=" * 70)

    print("\n✅ Example 1: Simple Chat")
    print("-" * 70)
    # example_simple_chat()

    print("\n✅ Example 2: Multi-turn Conversation")
    print("-" * 70)
    # example_multi_turn_conversation()

    print("\n✅ Example 3: Streaming Response")
    print("-" * 70)
    # example_streaming_response()

    print("\n✅ Example 4: JSON Response")
    print("-" * 70)
    # example_json_response()

    print("\n✅ Example 5: Thinking Process")
    print("-" * 70)
    # example_thinking_process()

    print("\n✅ Example 6: Token Estimation")
    print("-" * 70)
    example_estimate_tokens("How can I optimize my swarm simulation?")

    print("\n✅ Example 7: Error Handling")
    print("-" * 70)
    # example_error_handling()

    print("\n✅ Example 8: High-speed Model")
    print("-" * 70)
    # example_highspeed_model()

    print("\n✅ Example 9: MiroFish Integration")
    print("-" * 70)
    # example_mirofish_integration()

    print("\n" + "=" * 70)
    print("Note: Uncomment examples to run them (requires valid API key)")
    print("=" * 70)
