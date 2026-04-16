# 🚀 MiniMax M2.7 Integration Guide for MiroFish

## Overview

**MiniMax-M2.7** is a powerful LLM with:
- 📊 204,800 token context window
- 🎯 SOTA performance in programming & reasoning
- ⚡ ~60 tps output speed (M2.7-highspeed: ~100 tps)
- 🔄 Compatible with OpenAI SDK

This guide explains how to use MiniMax M2.7 in MiroFish using **Token Plan**.

---

## 1️⃣ Understanding MiniMax Token Plan

### Token Plan vs Pay-as-you-go

| Feature | Token Plan | Pay-as-you-go |
|---------|-----------|----------------|
| **API Key Type** | Exclusive Token Plan Key | Standard API Key |
| **Models** | All models | All models |
| **Billing** | Pre-paid tokens | Usage-based |
| **Duration** | Subscription period | Ongoing |
| **Interchangeability** | ❌ NOT with pay-as-you-go | ❌ NOT with Token Plan |

**⚠️ Important**: Token Plan and pay-as-you-go API keys are **NOT interchangeable**.

---

## 2️⃣ Getting Your MiniMax Token Plan API Key

### Step 1: Subscribe to Token Plan

1. Visit: https://platform.minimax.io/subscribe/token-plan
2. Choose your plan:
   - **Starter**: Limited tokens (good for testing)
   - **Plus**: Medium tokens
   - **Max**: Maximum tokens
3. Complete the subscription

### Step 2: Create API Key

1. Go to: https://platform.minimax.io/user-center/basic-information/interface-key
2. Click **"Create Token Plan Key"** (NOT "Create new secret key")
3. Copy your API Key immediately
4. Save it securely

### Step 3: Verify Your Subscription

- API Key is only valid during **active Token Plan subscription**
- Check your subscription status in Account Settings
- Renew before expiration

---

## 3️⃣ Configuration in MiroFish

### Option A: Using OpenAI Compatible API (Native)

Update `.env`:

```bash
# Using OpenAI-compatible endpoint
LLM_API_KEY=<YOUR_TOKEN_PLAN_API_KEY>
LLM_BASE_URL=https://api.minimax.io/v1
LLM_MODEL_NAME=MiniMax-M2.7
```

### Option B: Using Anthropic Compatible API (Recommended ✨)

Update `.env`:

```bash
# Using Anthropic-compatible endpoint (recommended)
LLM_API_KEY=<YOUR_TOKEN_PLAN_API_KEY>
LLM_BASE_URL=https://api.minimax.io/anthropic
LLM_MODEL_NAME=MiniMax-M2.7
```

### Available Models

```
MiniMax-M2.7              # Latest, ~60 tps
MiniMax-M2.7-highspeed    # Faster, ~100 tps (recommended for real-time)
MiniMax-M2.5              # Stable, ~60 tps
MiniMax-M2.5-highspeed    # Stable + fast, ~100 tps
MiniMax-M2.1              # Programming focused
MiniMax-M2.1-highspeed    # Programming + fast
MiniMax-M2                # Legacy, agentic
```

---

## 4️⃣ Code Integration

### Backend Configuration

The MiroFish backend **already supports** OpenAI/Anthropic compatible APIs!

File: `backend/app/config.py`

```python
# LLM配置（统一使用OpenAI格式）
LLM_API_KEY = os.environ.get('LLM_API_KEY')
LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
```

### LLM Client Usage

File: `backend/app/utils/llm_client.py`

The LLMClient already handles MiniMax M2.7:

```python
from openai import OpenAI

class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
```

**This automatically works with MiniMax!** ✅

---

## 5️⃣ API Calling Examples

### Python Example (MiroFish Backend)

```python
from backend.app.utils.llm_client import LLMClient

# Initialize client (uses .env config)
client = LLMClient()

# Simple chat
response = client.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is MiroFish?"}
    ],
    temperature=0.7,
    max_tokens=1024
)

print(response)
```

### With Streaming (Optional)

MiniMax supports streaming for real-time responses:

```python
from openai import OpenAI

client = OpenAI(
    api_key="<YOUR_TOKEN_PLAN_API_KEY>",
    base_url="https://api.minimax.io/v1"
)

stream = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Using Interleaved Thinking (M2.7 Feature)

MiniMax M2.7 includes thinking capabilities:

```python
from openai import OpenAI

client = OpenAI(
    api_key="<YOUR_TOKEN_PLAN_API_KEY>",
    base_url="https://api.minimax.io/v1"
)

response = client.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[{"role": "user", "content": "Complex reasoning task..."}],
    # Separate thinking content into reasoning_details
    extra_body={"reasoning_split": True}
)

# Access thinking process
thinking = response.choices[0].message.reasoning_details
content = response.choices[0].message.content
```

---

## 6️⃣ Important Notes for MiroFish

### ✅ Already Handled

The MiroFish backend already:
- ✅ Uses OpenAI SDK (compatible with MiniMax)
- ✅ Strips `<think>` tags from responses (line 66-67 in llm_client.py)
- ✅ Handles JSON responses
- ✅ Supports temperature and max_tokens

### ⚠️ Things to Know

1. **Temperature Range**: MiniMax accepts (0.0, 1.0], recommended: 1.0
2. **Token Limit**: Max 204,800 tokens per request
3. **Thinking Content**: M2.7 includes `<think>` tags (already cleaned)
4. **Multi-turn Conversations**: Preserve full assistant messages for reasoning chain continuity
5. **Cost**: Token Plan pricing differs from pay-as-you-go

### ❌ Not Supported

- `presence_penalty`, `frequency_penalty`, `logit_bias`
- Image/audio inputs (yet)
- `n` parameter (only value 1)
- Deprecated `function_call` (use `tools` instead)

---

## 7️⃣ Environment Setup

### Local Development

```bash
# .env file
LLM_API_KEY=minimax_token_plan_key_here
LLM_BASE_URL=https://api.minimax.io/v1
LLM_MODEL_NAME=MiniMax-M2.7
DEBUG=true
```

### Coolify Deployment

In Coolify Dashboard, set environment variables:

```
LLM_API_KEY=<your_token_plan_api_key>
LLM_BASE_URL=https://api.minimax.io/v1
LLM_MODEL_NAME=MiniMax-M2.7
DEBUG=false
```

---

## 8️⃣ Troubleshooting

### Issue: "API Key is invalid"

**Solution**: 
- Verify you're using **Token Plan API Key** (not pay-as-you-go)
- Check key is copied completely
- Ensure subscription is active

### Issue: "Model not found: MiniMax-M2.7"

**Solution**:
- Use exact model name: `MiniMax-M2.7` (case-sensitive)
- Verify API Key is valid
- Check Token Plan is active

### Issue: "Invalid base URL"

**Solution**:
- For OpenAI SDK: use `https://api.minimax.io/v1`
- For Anthropic SDK: use `https://api.minimax.io/anthropic`
- Ensure no trailing slashes

### Issue: Slow responses

**Solution**:
- Use `MiniMax-M2.7-highspeed` for faster responses (~100 tps)
- Reduce `max_tokens` if appropriate
- Check subscription plan limits

---

## 9️⃣ Testing Your Setup

### 1. Test API Connection

```bash
# Test with Python
python3 -c "
from openai import OpenAI
import os

client = OpenAI(
    api_key='<YOUR_TOKEN_PLAN_API_KEY>',
    base_url='https://api.minimax.io/v1'
)

response = client.chat.completions.create(
    model='MiniMax-M2.7',
    messages=[{'role': 'user', 'content': 'Hi'}],
    max_tokens=100
)
print('✅ Success!')
print(response.choices[0].message.content)
"
```

### 2. Test in MiroFish

```bash
# Run backend
npm run backend

# Test API endpoint
curl http://localhost:8000/api/test-llm
```

### 3. Monitor Token Usage

Visit: https://platform.minimax.io/user-center/basic-information/interface-key
- View token consumption
- Monitor subscription status
- Manage multiple API keys

---

## 🔟 Best Practices

### For Production (Coolify)

✅ **Do:**
- Use `MiniMax-M2.7-highspeed` for production (faster)
- Set `DEBUG=false`
- Monitor token usage regularly
- Test thoroughly before deployment
- Use reasonable `max_tokens` limits
- Cache API responses when possible

❌ **Don't:**
- Commit API keys to Git
- Use development API key in production
- Set unreasonable `max_tokens` values
- Leave `DEBUG=true` in production
- Share API keys

---

## 📚 Useful Links

| Resource | Link |
|----------|------|
| **Token Plan Docs** | https://platform.minimax.io/docs/token-plan/quickstart |
| **OpenAI Compatible API** | https://platform.minimax.io/docs/api-reference/text-openai-api |
| **Anthropic Compatible API** | https://platform.minimax.io/docs/api-reference/text-anthropic-api |
| **M2.7 for Coding** | https://platform.minimax.io/docs/guides/text-ai-coding-tools |
| **Subscribe** | https://platform.minimax.io/subscribe/token-plan |
| **Account** | https://platform.minimax.io/user-center/basic-information |

---

## Summary

To use MiniMax M2.7 in MiroFish:

1. ✅ Subscribe to Token Plan at https://platform.minimax.io/subscribe/token-plan
2. ✅ Create API Key at https://platform.minimax.io/user-center/basic-information/interface-key
3. ✅ Update `.env`:
   ```
   LLM_API_KEY=<your_token_plan_api_key>
   LLM_BASE_URL=https://api.minimax.io/v1
   LLM_MODEL_NAME=MiniMax-M2.7
   ```
4. ✅ Run `npm run backend` - it works automatically!

The MiroFish backend is **already compatible** with MiniMax M2.7! 🎉

---

**Last Updated**: 2026-04-16
**Integration Status**: ✅ Ready to Deploy
