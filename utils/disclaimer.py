"""
Disclaimer manager for adding warnings to LLM responses.
Support for all 18 languages
"""

import random
import logging

logger = logging.getLogger(__name__)


class DisclaimerManager:
    """Manage adding disclaimers to LLM responses in 18 languages"""

    def __init__(self):
        # Keywords for content detection (multilingual)
        self.price_keywords = [
            # RU/EN
            "лари", "цена", "стоимость", "билет", "$", "₾", "euro", "доллар",
            "бесплатно", "платно", "тариф", "cost", "price", "fee", "free", "рубль",
            # DE/FR/ES/IT
            "preis", "kostenlos", "prix", "gratuit", "precio", "gratis", "prezzo",
            # Other
            "ticket", "entrance", "admission"
        ]

        self.time_keywords = [
            # RU/EN
            "время работы", "открыт", "график", "часы", "расписание", "закрыт",
            "opening hours", "schedule", "closed", "open", "working time", "hours",
            # DE/FR/ES/IT
            "öffnungszeiten", "geschlossen", "horaires", "fermé", "horario", "cerrado",
            "orari", "chiuso"
        ]

        self.seasonal_keywords = [
            "зима", "снег", "горы", "трекинг", "лыжи", "альпинизм", "сезон",
            "winter", "snow", "hiking", "climbing", "ski", "mountain", "season",
            "sommer", "hiver", "invierno", "inverno", "estate"
        ]

        self.transport_keywords = [
            "маршрут", "добраться", "транспорт", "автобус", "поезд", "дорога",
            "route", "transport", "bus", "train", "car", "taxi", "road",
            "verkehr", "transports", "transporte"
        ]

        # Disclaimers in 18 languages
        self.disclaimers = {
            # English
            'en': {
                'price': "⚠️ **Note**: Prices may change. Please verify current costs before visiting.",
                'schedule': "🕒 **Note**: Opening hours may vary by season and holidays. Please check current schedule.",
                'seasonal': "🌨️ **Important**: Mountain route accessibility depends on weather and season. Check conditions before traveling.",
                'transport': "🚌 **Tip**: Public transport routes may change. Verify current schedules and routes.",
                'general': "🗺️ **Please note**: Information may be incomplete or outdated. Always verify current details before planning your trip."
            },

            # Russian
            'ru': {
                'price': "⚠️ **Внимание**: Цены могут изменяться. Рекомендуем уточнить актуальную стоимость перед посещением.",
                'schedule': "🕒 **Примечание**: Время работы может изменяться в зависимости от сезона и праздников. Уточняйте актуальное расписание.",
                'seasonal': "🌨️ **Важно**: Доступность горных маршрутов зависит от погодных условий и сезона. Проверяйте условия перед поездкой.",
                'transport': "🚌 **Совет**: Маршруты общественного транспорта могут изменяться. Проверьте актуальное расписание и маршруты.",
                'general': "🗺️ **Обратите внимание**: Информация может быть неполной или устаревшей. Всегда проверяйте актуальные данные перед планированием поездки."
            },

            # Georgian
            'ka': {
                'price': "⚠️ **ყურადღება**: ფასები შეიძლება შეიცვალოს. გთხოვთ, გადაამოწმოთ ფასები ვიზიტამდე.",
                'schedule': "🕒 **შენიშვნა**: სამუშაო საათები შეიძლება იცვლებოდეს სეზონისა და დღესასწაულების მიხედვით.",
                'seasonal': "🌨️ **მნიშვნელოვანი**: მთის მარშრუტების ხელმისაწვდომობა დამოკიდებულია ამინდსა და სეზონზე.",
                'transport': "🚌 **რჩევა**: საზოგადოებრივი ტრანსპორტის მარშრუტები შეიძლება შეიცვალოს.",
                'general': "🗺️ **გთხოვთ გაითვალისწინოთ**: ინფორმაცია შეიძლება იყოს არასრული ან მოძველებული."
            },

            # German
            'de': {
                'price': "⚠️ **Hinweis**: Preise können sich ändern. Bitte aktuelle Kosten vor dem Besuch prüfen.",
                'schedule': "🕒 **Hinweis**: Öffnungszeiten können saisonal und an Feiertagen variieren.",
                'seasonal': "🌨️ **Wichtig**: Bergwege-Zugänglichkeit hängt von Wetter und Jahreszeit ab.",
                'transport': "🚌 **Tipp**: Öffentliche Verkehrsmittel können sich ändern. Aktuelle Fahrpläne prüfen.",
                'general': "🗺️ **Bitte beachten**: Informationen können unvollständig oder veraltet sein."
            },

            # French
            'fr': {
                'price': "⚠️ **Attention**: Les prix peuvent changer. Vérifiez les tarifs actuels avant votre visite.",
                'schedule': "🕒 **Note**: Les horaires peuvent varier selon la saison et les jours fériés.",
                'seasonal': "🌨️ **Important**: L'accès aux itinéraires de montagne dépend de la météo et de la saison.",
                'transport': "🚌 **Conseil**: Les itinéraires de transport public peuvent changer. Vérifiez les horaires actuels.",
                'general': "🗺️ **Veuillez noter**: Les informations peuvent être incomplètes ou obsolètes."
            },

            # Spanish
            'es': {
                'price': "⚠️ **Atención**: Los precios pueden cambiar. Verifique los costos actuales antes de visitar.",
                'schedule': "🕒 **Nota**: Los horarios pueden variar según la temporada y los días festivos.",
                'seasonal': "🌨️ **Importante**: La accesibilidad de las rutas de montaña depende del clima y la temporada.",
                'transport': "🚌 **Consejo**: Las rutas de transporte público pueden cambiar. Verifique los horarios actuales.",
                'general': "🗺️ **Por favor note**: La información puede estar incompleta o desactualizada."
            },

            # Italian
            'it': {
                'price': "⚠️ **Attenzione**: I prezzi possono cambiare. Verificare i costi attuali prima della visita.",
                'schedule': "🕒 **Nota**: Gli orari di apertura possono variare per stagione e festività.",
                'seasonal': "🌨️ **Importante**: L'accessibilità dei percorsi montani dipende dal meteo e dalla stagione.",
                'transport': "🚌 **Suggerimento**: Le rotte dei trasporti pubblici possono cambiare. Verificare gli orari attuali.",
                'general': "🗺️ **Si prega di notare**: Le informazioni potrebbero essere incomplete o obsolete."
            },

            # Dutch
            'nl': {
                'price': "⚠️ **Let op**: Prijzen kunnen veranderen. Controleer de huidige kosten voor uw bezoek.",
                'schedule': "🕒 **Opmerking**: Openingstijden kunnen variëren per seizoen en feestdagen.",
                'seasonal': "🌨️ **Belangrijk**: Toegankelijkheid van bergroutes hangt af van het weer en seizoen.",
                'transport': "🚌 **Tip**: Openbaar vervoerroutes kunnen wijzigen. Controleer actuele dienstregelingen.",
                'general': "🗺️ **Let op**: Informatie kan onvolledig of verouderd zijn."
            },

            # Polish
            'pl': {
                'price': "⚠️ **Uwaga**: Ceny mogą się zmieniać. Sprawdź aktualne koszty przed wizytą.",
                'schedule': "🕒 **Uwaga**: Godziny otwarcia mogą się zmieniać w zależności od sezonu i świąt.",
                'seasonal': "🌨️ **Ważne**: Dostępność tras górskich zależy od pogody i sezonu.",
                'transport': "🚌 **Wskazówka**: Trasy transportu publicznego mogą się zmieniać. Sprawdź aktualne rozkłady.",
                'general': "🗺️ **Proszę zauważyć**: Informacje mogą być niekompletne lub nieaktualne."
            },

            # Czech
            'cs': {
                'price': "⚠️ **Upozornění**: Ceny se mohou měnit. Ověřte aktuální náklady před návštěvou.",
                'schedule': "🕒 **Poznámka**: Otevírací doba se může měnit podle sezóny a svátků.",
                'seasonal': "🌨️ **Důležité**: Přístupnost horských tras závisí na počasí a sezóně.",
                'transport': "🚌 **Tip**: Trasy veřejné dopravy se mohou měnit. Ověřte aktuální jízdní řády.",
                'general': "🗺️ **Upozornění**: Informace mohou být neúplné nebo zastaralé."
            },

            # Chinese
            'zh': {
                'price': "⚠️ **注意**：价格可能会变化。请在访问前确认最新价格。",
                'schedule': "🕒 **注意**：营业时间可能因季节和节假日而异。",
                'seasonal': "🌨️ **重要**：山区路线的可达性取决于天气和季节。",
                'transport': "🚌 **提示**：公共交通路线可能会变化。请确认最新时刻表。",
                'general': "🗺️ **请注意**：信息可能不完整或过时。"
            },

            # Japanese
            'ja': {
                'price': "⚠️ **注意**：料金は変更される場合があります。訪問前に最新の料金をご確認ください。",
                'schedule': "🕒 **注意**：営業時間は季節や祝日により変更される場合があります。",
                'seasonal': "🌨️ **重要**：山岳ルートへのアクセスは天候と季節によります。",
                'transport': "🚌 **ヒント**：公共交通機関のルートは変更される場合があります。",
                'general': "🗺️ **ご注意ください**：情報は不完全または古い可能性があります。"
            },

            # Korean
            'ko': {
                'price': "⚠️ **주의**: 가격은 변경될 수 있습니다. 방문 전 최신 요금을 확인하세요.",
                'schedule': "🕒 **참고**: 운영 시간은 계절과 공휴일에 따라 달라질 수 있습니다.",
                'seasonal': "🌨️ **중요**: 산악 경로 접근성은 날씨와 계절에 따라 다릅니다.",
                'transport': "🚌 **팁**: 대중교통 노선은 변경될 수 있습니다. 최신 시간표를 확인하세요.",
                'general': "🗺️ **참고하세요**: 정보가 불완전하거나 오래되었을 수 있습니다."
            },

            # Arabic
            'ar': {
                'price': "⚠️ **تنبيه**: قد تتغير الأسعار. يرجى التحقق من التكاليف الحالية قبل الزيارة.",
                'schedule': "🕒 **ملاحظة**: قد تختلف ساعات العمل حسب الموسم والعطلات.",
                'seasonal': "🌨️ **هام**: تعتمد إمكانية الوصول إلى الطرق الجبلية على الطقس والموسم.",
                'transport': "🚌 **نصيحة**: قد تتغير خطوط النقل العام. تحقق من الجداول الحالية.",
                'general': "🗺️ **يرجى ملاحظة**: قد تكون المعلومات غير كاملة أو قديمة."
            },

            # Turkish
            'tr': {
                'price': "⚠️ **Dikkat**: Fiyatlar değişebilir. Ziyaretten önce güncel fiyatları kontrol edin.",
                'schedule': "🕒 **Not**: Açılış saatleri mevsime ve tatil günlerine göre değişebilir.",
                'seasonal': "🌨️ **Önemli**: Dağ rotalarına erişim hava durumu ve mevsime bağlıdır.",
                'transport': "🚌 **İpucu**: Toplu taşıma güzergahları değişebilir. Güncel tarifeleri kontrol edin.",
                'general': "🗺️ **Lütfen dikkat**: Bilgiler eksik veya güncel olmayabilir."
            },

            # Hindi
            'hi': {
                'price': "⚠️ **ध्यान दें**: कीमतें बदल सकती हैं। यात्रा से पहले वर्तमान लागत सत्यापित करें।",
                'schedule': "🕒 **नोट**: खुलने का समय मौसम और छुट्टियों के अनुसार भिन्न हो सकता है।",
                'seasonal': "🌨️ **महत्वपूर्ण**: पहाड़ी मार्गों की पहुंच मौसम और ऋतु पर निर्भर करती है।",
                'transport': "🚌 **सुझाव**: सार्वजनिक परिवहन मार्ग बदल सकते हैं। वर्तमान समय सारणी जांचें।",
                'general': "🗺️ **कृपया ध्यान दें**: जानकारी अधूरी या पुरानी हो सकती है।"
            },

            # Armenian
            'hy': {
                'price': "⚠️ **Ուշադրություն**: Գները կարող են փոխվել։ Այցից առաջ ստուգեք ընթացիկ գները։",
                'schedule': "🕒 **Նշում**: Աշխատանքային ժամերը կարող են տարբերվել սեզոնի և տոների համաձայն։",
                'seasonal': "🌨️ **Կարևոր**: Լեռնային երթուղիների հասանելիությունը կախված է եղանակից և սեզոնից։",
                'transport': "🚌 **Խորհուրդ**: Հասարակական տրանսպորտի երթուղիները կարող են փոխվել։",
                'general': "🗺️ **Խնդրում ենք նկատի ունենալ**: Տեղեկատվությունը կարող է անամբողջական կամ հնացած լինել։"
            },

            # Azerbaijani
            'az': {
                'price': "⚠️ **Diqqət**: Qiymətlər dəyişə bilər. Ziyarətdən əvvəl cari xərcləri yoxlayın.",
                'schedule': "🕒 **Qeyd**: İş saatları mövsümə və bayramlara görə dəyişə bilər.",
                'seasonal': "🌨️ **Vacib**: Dağ marşrutlarına çıxış hava şəraiti və mövsümdən asılıdır.",
                'transport': "🚌 **Məsləhət**: İctimai nəqliyyat marşrutları dəyişə bilər.",
                'general': "🗺️ **Nəzərə alın**: Məlumat natamam və ya köhnəlmiş ola bilər."
            }
        }

        self.disclaimer_frequency = 1.0  # 100% disclaimer adding

    def detect_content_types(self, answer):
        """Detect content types in response"""
        content_types = []
        answer_lower = answer.lower()

        if any(keyword in answer_lower for keyword in self.price_keywords):
            content_types.append('price')

        if any(keyword in answer_lower for keyword in self.time_keywords):
            content_types.append('schedule')

        if any(keyword in answer_lower for keyword in self.seasonal_keywords):
            content_types.append('seasonal')

        if any(keyword in answer_lower for keyword in self.transport_keywords):
            content_types.append('transport')

        return content_types

    def add_disclaimers(self, answer, language='en'):
        """
        Add appropriate disclaimers to response in target language.

        Args:
            answer: Response text
            language: Target language code (en, ru, ka, de, etc.)

        Returns:
            Answer with disclaimers in target language
        """
        # Fallback to English if language not supported
        if language not in self.disclaimers:
            logger.warning(f"Language {language} not supported for disclaimers, using English")
            language = 'en'

        content_types = self.detect_content_types(answer)

        if not content_types:
            # If no specific content, add general disclaimer in 30% of cases
            if random.random() < 0.3:
                return f"{answer}\n\n{self.disclaimers[language]['general']}"
            return answer

        # Add specific disclaimers in target language
        disclaimer_sections = []
        for content_type in set(content_types):  # Remove duplicates
            if content_type in self.disclaimers[language]:
                disclaimer_sections.append(self.disclaimers[language][content_type])

        if disclaimer_sections:
            # Header in target language
            headers = {
                'en': "### ⚠️ Important Information:",
                'ru': "### ⚠️ Важная информация:",
                'ka': "### ⚠️ მნიშვნელოვანი ინფორმაცია:",
                'de': "### ⚠️ Wichtige Information:",
                'fr': "### ⚠️ Information importante:",
                'es': "### ⚠️ Información importante:",
                'it': "### ⚠️ Informazioni importanti:",
                'nl': "### ⚠️ Belangrijke informatie:",
                'pl': "### ⚠️ Ważne informacje:",
                'cs': "### ⚠️ Důležité informace:",
                'zh': "### ⚠️ 重要信息：",
                'ja': "### ⚠️ 重要な情報：",
                'ko': "### ⚠️ 중요 정보:",
                'ar': "### ⚠️ معلومات هامة:",
                'tr': "### ⚠️ Önemli Bilgi:",
                'hi': "### ⚠️ महत्वपूर्ण जानकारी:",
                'hy': "### ⚠️ Կարևոր տեղեկատվություն:",
                'az': "### ⚠️ Vacib məlumat:"
            }

            header = headers.get(language, headers['en'])
            disclaimer_text = f"\n\n---\n\n{header}\n\n" + "\n\n".join(disclaimer_sections)
            return answer + disclaimer_text

        return answer