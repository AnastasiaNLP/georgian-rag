"""
Enhanced response generator with Claude API and LangSmith tracing.
"""

import logging
import asyncio
from typing import Dict, Any

from anthropic import AsyncAnthropic
from langsmith import Client, traceable

logger = logging.getLogger(__name__)


class EnhancedResponseGenerator:
    """
    Response generator with optimized language instructions.

    STRATEGY:
    1. Documents stay in original language (RU/EN) - NO translation
    2. LLM generates response DIRECTLY in target_language
    3. NO final translation needed

    Features:
    - AsyncAnthropic - non-blocking Claude API calls
    - Direct multilingual generation (18 languages)
    - Optimized language instructions
    - max_tokens=800
    - Streaming-ready structure
    """

    def __init__(self, anthropic_api_key: str, langsmith_api_key: str,
                 multilingual_manager,
                 disclaimer_manager=None):
        """
        Initialize ResponseGenerator.

        Args:
            anthropic_api_key: Claude API key
            langsmith_api_key: LangSmith API key
            multilingual_manager: MultilingualManager instance
            disclaimer_manager: Optional DisclaimerManager
        """
        self.claude_client = AsyncAnthropic(api_key=anthropic_api_key)
        self.langsmith_client = Client(api_key=langsmith_api_key)
        self.multilingual = multilingual_manager
        self.disclaimer_manager = disclaimer_manager

        logger.info("EnhancedResponseGenerator initialized with AsyncAnthropic")

    @traceable(name="generate_tourism_response")
    async def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response directly in target language.

        Flow:
        1. Build prompt with language instruction
        2. LLM generates DIRECTLY in target_language
        3. Return response (NO translation)
        """

        query_info = context["query_info"]
        target_language = query_info["target_language"]

        try:
            logger.info(f"Building prompt for target language: {target_language}")
            prompt = await self._build_multilingual_prompt(context, target_language)

            logger.info(f"Calling Claude API (async) for {target_language}...")
            response = await asyncio.wait_for(
                self._call_claude_api_async(prompt),
                timeout=30.0
            )

            response_text = response.content[0].text
            logger.info(f"LLM generated response in {target_language} ({len(response_text)} chars)")

            if self.disclaimer_manager:
                response_text = self.disclaimer_manager.add_disclaimers(response_text)

                if target_language not in ["ru", "en"]:
                    response_text = await self._translate_disclaimers(response_text, target_language)

            return {
                "response": response_text,
                "language": target_language,
                "token_usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                "enrichment_used": bool(context["enrichment"]),
                "images_available": len(context["images"]),
                "generation_info": {
                    "direct_generation": True,
                    "llm_language": target_language,
                    "translation_used": False
                }
            }

        except asyncio.TimeoutError:
            logger.error(f"Response generation timeout for {target_language}")
            return {
                "response": await self._get_timeout_message(target_language),
                "error": "timeout",
                "language": target_language
            }
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "response": await self._get_error_message(target_language),
                "error": str(e),
                "language": target_language
            }

    async def _call_claude_api_async(self, prompt: str):
        """ASYNC Claude API call - fully non-blocking"""
        return await self.claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

    async def _build_multilingual_prompt(self, context: Dict, target_language: str) -> str:
        """
        Build prompt with OPTIMIZED language instruction from MultilingualManager.

        Strategy: English base prompt + OPTIMIZED language enforcement
        """

        query_info = context["query_info"]
        intent = query_info.get("intent", "info_request")

        english_prompts = self._get_english_base_prompts()
        base_prompt = english_prompts.get(intent, english_prompts.get("info_request"))

        filled_prompt = self._fill_prompt_template(base_prompt, context)

        language_instruction = self.multilingual.get_optimized_language_instruction(target_language)

        return f"{language_instruction}\n\n{filled_prompt}"

    def _get_english_base_prompts(self) -> Dict[str, str]:
        """
        Base prompts in English (for all intents).

        These will be combined with the language instruction
        to create the final multilingual prompt.
        """
        return {
            "info_request": """You are an expert Georgian tourism guide. A user asked: "{query}"

RELEVANT INFORMATION ({total_results} results):
{results}

ADDITIONAL DETAILS:
{enrichment}

AVAILABLE VISUALS:
{images}

INSTRUCTIONS:
- Provide comprehensive, engaging information (200-300 words)
- Use markdown formatting (headers, lists, emojis)
- Highlight unique cultural aspects
- Be enthusiastic and inspiring
- Reference available photos when relevant
- Include practical tips if applicable

Create an amazing response that makes them want to visit!""",

            "recommendation": """You are an expert Georgian tourism guide helping with recommendations: "{query}"

RELEVANT INFORMATION ({total_results} results):
{results}

ADDITIONAL DETAILS:
{enrichment}

AVAILABLE VISUALS:
{images}

INSTRUCTIONS:
- Suggest top 3-5 best options based on their interests
- Explain WHY each recommendation fits their needs
- Provide practical details (location, accessibility, best time)
- Use engaging, persuasive language (200-300 words)
- Include cultural context
- Reference available photos

Help them discover the perfect Georgian experience!""",

            "route_planning": """You are an expert Georgian tourism guide helping plan an itinerary: "{query}"

RELEVANT INFORMATION ({total_results} results):
{results}

ADDITIONAL DETAILS:
{enrichment}

AVAILABLE VISUALS:
{images}

INSTRUCTIONS:
- Create a logical, efficient route/plan
- Include travel times and practical logistics
- Suggest optimal visiting times
- Highlight must-see vs optional stops
- Provide insider tips (200-300 words)
- Make it realistic and enjoyable

Design the perfect Georgian adventure!""",

            "follow_up": """You are continuing a conversation about Georgian tourism: "{query}"

RELEVANT INFORMATION ({total_results} results):
{results}

ADDITIONAL DETAILS:
{enrichment}

AVAILABLE VISUALS:
{images}

INSTRUCTIONS:
- Provide additional relevant information (150-200 words)
- Build on previous conversation context
- Include new details not mentioned before
- Keep enthusiastic, helpful tone
- Reference available photos

Continue helping them explore Georgia!"""
        }

    def _fill_prompt_template(self, template: str, context: Dict) -> str:
        """
        Fill prompt template with context data.

        OPTIMIZED: Trim descriptions to avoid token limits
        """

        results_text = ""
        for result in context["search_results"][:3]:
            description = result['description']
            trimmed_desc = description[:300] + '...' if len(description) > 300 else description

            image_info = ""
            if result.get('image_url'):
                image_info = f"\n📸 Photo available: {result['image_url']}"
            results_text += f"""
Name: {result['name']}
Description: {trimmed_desc}
Category: {result['category']}
Location: {result['location']}
Relevance: {result['score']:.3f}

"""

        enrichment_text = ""
        if context["enrichment"]:
            enrichment = context["enrichment"]
            if enrichment.get("wikipedia_content"):
                wiki_content = enrichment['wikipedia_content'][:200] + '...'
                enrichment_text += f"Additional Info: {wiki_content}\n\n"

        images_info = ""
        if context["images"]:
            images_list = []
            for img in context["images"][:5]:
                if img.get("url"):
                    source_icon = "🗄️" if img.get("source") == "database" else "📸"
                    location = img.get("location", "Unknown")
                    images_list.append(f"{source_icon} {location}: {img['url']}")
            if images_list:
                images_info = "Available photos:\n" + "\n".join(images_list)
            else:
                images_info = "Photos are available but URLs not provided"
        else:
            images_info = "No photos available"

        return template.format(
            query=context["query_info"]["original_query"],
            language=context["metadata_summary"]["language_info"]["language_name"],
            results=results_text,
            enrichment=enrichment_text,
            images=images_info,
            total_results=context["metadata_summary"]["total_results"]
        )

    async def _translate_disclaimers(self, text: str, target_language: str) -> str:
        """Translate only disclaimer text (not full response)"""
        if target_language in ["ru", "en"]:
            return text

        try:
            if "⚠️" in text or "disclaimer" in text.lower():
                translated = await self.multilingual.translate_if_needed(
                    text,
                    target_language,
                    "en",
                    is_permanent=False
                )
                return translated
        except Exception as e:
            logger.warning(f"Disclaimer translation failed: {e}")

        return text

    async def _get_error_message(self, language: str) -> str:
        """Error messages in all 18 languages"""
        messages = {
            "en": "I apologize, but I encountered a technical error. Please try again.",
            "ru": "Извините, произошла техническая ошибка. Пожалуйста, попробуйте еще раз.",
            "ka": "ვწუხვარ, მოხდა ტექნიკური შეცდომა. გთხოვთ, სცადოთ ხელახლა.",
            "de": "Entschuldigung, es ist ein technischer Fehler aufgetreten. Bitte versuchen Sie es erneut.",
            "fr": "Désolé, une erreur technique s'est produite. Veuillez réessayer.",
            "es": "Lo siento, ha ocurrido un error técnico. Por favor, inténtelo de nuevo.",
            "it": "Mi dispiaccio, si è verificato un errore tecnico. Per favore, riprova.",
            "nl": "Sorry, er is een technische fout opgetreden. Probeer het opnieuw.",
            "pl": "Przepraszam, wystąpił błąd techniczny. Proszę spróbować ponownie.",
            "cs": "Omlouváme se, došlo k technické chybě. Zkuste to prosím znovu.",
            "zh": "抱歉，发生了技术错误。请重试。",
            "ja": "申し訳ございません。技術的なエラーが発生しました。もう一度お試しください。",
            "ko": "죄송합니다. 기술적 오류가 발생했습니다. 다시 시도해 주세요.",
            "ar": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
            "tr": "Üzgünüm, teknik bir hata oluştu. Lütfen tekrar deneyin.",
            "hi": "क्षमा करें, एक तकनीकी त्रुटि हुई। कृपया पुनः प्रयास करें।",
            "hy": "Ներողություն, տեխնիկական սխալ է տեղի ունեցել: Խնդրում ենք նորից փորձել:",
            "az": "Üzr istəyirik, texniki xəta baş verdi. Zəhmət olmasa yenidən cəhd edin."
        }
        return messages.get(language, messages["en"])

    async def _get_timeout_message(self, language: str) -> str:
        """Timeout messages in all 18 languages"""
        messages = {
            "en": "I apologize, but the request timed out. Please try again with a simpler question.",
            "ru": "Извините, запрос превысил время ожидания. Пожалуйста, попробуйте задать более простой вопрос.",
            "ka": "ვწუხვარ, მოთხოვნის დრო ამოიწურა. გთხოვთ, სცადოთ უფრო მარტივი კითხვა.",
            "de": "Entschuldigung, die Anfrage hat das Zeitlimit überschritten. Bitte versuchen Sie es mit einer einfacheren Frage.",
            "fr": "Désolé, la demande a expiré. Veuillez réessayer avec une question plus simple.",
            "es": "Lo siento, la solicitud ha excedido el tiempo. Por favor, intente con una pregunta más simple.",
            "it": "Mi dispiaccio, la richiesta è scaduta. Per favore, riprova con una domanda più semplice.",
            "nl": "Sorry, het verzoek is verlopen. Probeer het opnieuw met een eenvoudigere vraag.",
            "pl": "Przepraszam, żądanie przekroczyło czas. Proszę spróbować prostsze pytanie.",
            "cs": "Omlouváme se, požadavek vypršel. Zkuste to prosím s jednoduší otázkou.",
            "zh": "抱歉，请求超时。请尝试更简单的问题。",
            "ja": "申し訳ございません。リクエストがタイムアウトしました。より簡単な質問でお試しください。",
            "ko": "죄송합니다. 요청 시간이 초과되었습니다. 더 간단한 질문으로 다시 시도해 주세요.",
            "ar": "عذراً، انتهت مهلة الطلب. يرجى المحاولة بسؤال أبسط.",
            "tr": "Üzgünüm, istek zaman aşımına uğradı. Lütfen daha basit bir soruyla tekrar deneyin.",
            "hi": "क्षमा करें, अनुरोध समय समाप्त हो गया। कृपया एक सरल प्रश्न के साथ पुनः प्रयास करें।",
            "hy": "Ներողություն, հարցումը ժամանակից դուրս է: Խնդրում ենք փորձել ավելի պարզ հարցով:",
            "az": "Üzr istəyirik, sorğunun vaxtı bitdi. Zəhmət olmasa daha sadə bir sualla yenidən cəhd edin."
        }
        return messages.get(language, messages["en"])