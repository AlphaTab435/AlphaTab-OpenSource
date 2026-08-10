# API Setup Guide

The AI scoring engine requires API keys to connect to the cloud AI models. These keys are stored safely in your `.env` file.

Our system uses a **3-Tier Fallback Architecture** to ensure you never run out of free AI quotas:
1. **Groq** (Primary)
2. **Gemini** (Secondary)
3. **OpenRouter** (Backup)

---

## 1. How to get the Groq API Key (Primary AI)
Groq acts as our primary, highly-accurate scoring engine because it is blazing fast and completely free (though it has strict daily rate limits).
1. Go to **[console.groq.com](https://console.groq.com)**.
2. Sign in using your Google or GitHub account.
3. On the left-hand sidebar, click on **API Keys**.
4. Click the **Create API Key** button.
5. Copy the key it gives you (it will start with `gsk_`) and paste it into line 2 of your `.env` file.

## 2. How to get the Gemini API Key (Secondary AI)
When Groq hits its daily limit, the system automatically seamlessly fails over to Google Gemini. Gemini 3.1 Flash/Pro is extremely smart and has a generous free tier.
1. Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)**.
2. Sign in with your Google account.
3. Click the **Create API Key** button.
4. Copy the key it gives you and paste it into line 4 of your `.env` file.

## 3. What is OpenRouter? (Backup AI)
OpenRouter is not an AI itself—it is an "API Router" or middleman. It gives you access to hundreds of different AI models using just one API key. In our `config.yaml` file, we use `openrouter/free` as our absolute final safety net when both Groq and Gemini run out of free credits.

> **⚠️ WARNING: OpenRouter Free Tier Quality Issues**
> The `openrouter/free` roulette system routes to unpredictable models that sometimes hallucinate scores or break JSON parsing. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for full details on this behavior and how the codebase protects your database.

### Is the OpenRouter free tier generous?
Yes, it is incredibly generous! OpenRouter provides a completely 100% free, unlimited tier for certain open-source models (like Google Gemma and NVIDIA Nemotron). Because it costs exactly $0.00, it is the absolute perfect backup.

You can view the live, constantly updated list of all currently free models here:
**[OpenRouter Free Models List](https://openrouter.ai/models?max_price=0)**

#### How to get the OpenRouter API Key
1. Go to **[openrouter.ai](https://openrouter.ai/)**.
2. Sign in using Google or your email.
3. Click on your profile picture in the top right corner and select **Keys**.
4. Click the **Create Key** button.
5. Copy the key it gives you (it will usually start with `sk-or-v1-`) and paste it into line 3 of your `.env` file.
