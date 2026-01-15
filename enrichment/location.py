"""
Location extractor for Georgian attractions.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LocationExtractor:
    """
    Component for proper location information extraction from metadata.
    """

    def __init__(self):
        # priority Georgian locations for quick recognition
        self.priority_locations = {
            'тбилиси', 'tbilisi', 'თბილისი',
            'мцхета', 'mtskheta', 'მცხეთა',
            'батуми', 'batumi', 'ბათუმი',
            'кутаиси', 'kutaisi', 'ქუთაისი',
            'сигнахи', 'signagi', 'სიღნაღი',
            'гори', 'gori', 'გორი',
            'ахалкалаки', 'akhalkalaki',
            'боржоми', 'borjomi', 'ბორჯომი',
            'кобулети', 'kobuleti',
            'ахалцихе', 'akhaltsikhe',
            'зугдиди', 'zugdidi',
            'телави', 'telavi',
            'поти', 'poti',
            'рустави', 'rustavi'
        }

        # regional markers
        self.regional_markers = {
            'кахетия': ['кахетия', 'kakheti', 'კახეთი'],
            'самегрело': ['самегрело', 'samegrelo', 'სამეგრელო'],
            'сванетия': ['сванетия', 'svaneti', 'სვანეთი'],
            'аджария': ['аджария', 'adjara', 'აჭარა'],
            'имеретия': ['имеретия', 'imereti', 'იმერეთი'],
            'шида-картли': ['шида картли', 'shida kartli', 'inner kartli'],
            'самцхе-джавахети': ['самцхе', 'javakheti', 'джавахети']
        }

        logger.info("LocationExtractor initialized with new Qdrant structure support")

    def extract_location(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main location extraction function with multiple sources.
        Returns:
            Dict with keys: 'primary_location', 'all_locations', 'region', 'confidence'
        """
        result = {
            'primary_location': 'неизвестно',
            'all_locations': [],
            'region': None,
            'confidence': 0.0
        }

        # text-based location field
        location_text = metadata.get('location', '')

        if location_text and isinstance(location_text, str) and location_text.strip():
            # extract city/region from text address
            extracted_city = self._extract_city_from_address(location_text)

            if extracted_city:
                result['primary_location'] = extracted_city
                result['all_locations'].append(extracted_city)
                result['region'] = self._determine_region([extracted_city])
                result['confidence'] = 0.95  # High confidence

                logger.debug(f"Extracted location from address: {extracted_city}")
                return self._normalize_result(result)

        # fallback
        # ner_locations
        ner_locations = self._extract_from_ner(metadata)
        if ner_locations:
            result['all_locations'].extend(ner_locations)
            result['primary_location'] = ner_locations[0]
            result['confidence'] = 0.9

        # location flags
        flag_location = self._extract_from_location_flags(metadata)
        if flag_location and result['confidence'] < 0.7:
            result['primary_location'] = flag_location
            result['confidence'] = 0.8
            if flag_location not in result['all_locations']:
                result['all_locations'].append(flag_location)

        # tags
        tag_locations = self._extract_from_tags(metadata)
        if tag_locations:
            for loc in tag_locations:
                if loc not in result['all_locations']:
                    result['all_locations'].append(loc)
            if result['confidence'] < 0.5:
                result['primary_location'] = tag_locations[0]
                result['confidence'] = 0.6

        # name analysis
        name_location = self._extract_from_name(metadata)
        if name_location and result['confidence'] < 0.4:
            result['primary_location'] = name_location
            result['confidence'] = 0.5
            if name_location not in result['all_locations']:
                result['all_locations'].append(name_location)

        # determine region
        if not result['region']:
            result['region'] = self._determine_region(result['all_locations'])

        # final cleanup
        return self._normalize_result(result)

    def _extract_city_from_address(self, address: str) -> Optional[str]:
        """

        Examples:
        - "100 David Aghmashenebeli Ave, Kobuleti, Adjara, Georgia" → "Kobuleti"
        - "22 Pavle Ingorokva Street, Tbilisi, Georgia" → "Tbilisi"
        - "Центральная Грузия, регионы Имерети" → "Имерети"
        """
        if not address:
            return None

        address_lower = address.lower()

        # search for priority cities in address
        for location in self.priority_locations:
            if location in address_lower:
                # return properly capitalized
                return location.title()

        # parse address by commas (usually: street, city, region, country)
        parts = [p.strip() for p in address.split(',')]

        # skip "Georgia" and too long parts (streets)
        for part in parts:
            part_lower = part.lower()

            # skip Georgia, region words, long strings
            if 'georgia' in part_lower or 'грузия' in part_lower:
                continue
            if 'region' in part_lower or 'регион' in part_lower:
                continue
            if len(part) > 50:
                continue

            # check known cities
            for location in self.priority_locations:
                if location in part_lower:
                    return location.title()

            # check regions
            for region, markers in self.regional_markers.items():
                for marker in markers:
                    if marker in part_lower:
                        return marker.title()

        # if nothing found, take second part (usually city)
        if len(parts) >= 2:
            potential_city = parts[1].strip()
            # make sure it's not region/country
            if potential_city and len(potential_city) < 30:
                # check it's not a common word
                skip_words = ['georgia', 'грузия', 'region', 'регион', 'municipality', 'муниципалитет']
                if not any(skip in potential_city.lower() for skip in skip_words):
                    return potential_city.title()

        return None

    def _extract_from_ner(self, metadata: Dict[str, Any]) -> List[str]:
        """Extract from ner_locations field (old source)"""
        locations = []

        ner_fields = ['ner_locations', 'ner', 'locations']

        for field in ner_fields:
            if field in metadata:
                ner_data = metadata[field]

                if isinstance(ner_data, list):
                    for item in ner_data:
                        if isinstance(item, str) and len(item) > 1:
                            cleaned = self._clean_location_name(item)
                            if cleaned and self._is_valid_location(cleaned):
                                locations.append(cleaned)

                elif isinstance(ner_data, dict):
                    if 'locations' in ner_data:
                        for loc in ner_data['locations']:
                            cleaned = self._clean_location_name(loc)
                            if cleaned and self._is_valid_location(cleaned):
                                locations.append(cleaned)

        return self._sort_by_priority(locations)

    def _extract_from_location_flags(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract from special flags"""

        location_flags = {
            'is_tbilisi_related': 'Тбилиси',
            'is_mtskheta_related': 'Мцхета',
            'is_tbilisi_attraction': 'Тбилиси',
            'is_mtskheta_attraction': 'Мцхета'
        }

        for flag, location in location_flags.items():
            if metadata.get(flag, False):
                return location

        return None

    def _extract_from_tags(self, metadata: Dict[str, Any]) -> List[str]:
        """Extract from tags"""
        locations = []
        tags_fields = ['tags', 'tags_other']

        for field in tags_fields:
            if field in metadata:
                tags = metadata[field]
                if isinstance(tags, list):
                    for tag in tags:
                        if isinstance(tag, str):
                            cleaned = self._clean_location_name(tag)
                            if cleaned and self._is_valid_location(cleaned):
                                locations.append(cleaned)

        return self._sort_by_priority(locations)

    def _extract_from_name(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract location from attraction name"""
        name = metadata.get('name', '')
        if not name:
            return None

        name_lower = name.lower()

        # search for known locations in name
        for location in self.priority_locations:
            if location in name_lower:
                return location.title()

        # search for regional markers
        for region, markers in self.regional_markers.items():
            for marker in markers:
                if marker in name_lower:
                    return marker.title()

        return None

    def _clean_location_name(self, location: str) -> str:
        """Clean location name from artifacts"""
        if not isinstance(location, str):
            return ""

        cleaned = location.strip()

        # remove obvious NER artifacts
        artifacts = ['3136', 'см', 'км', 'м', 'комплекс эрозионных']
        for artifact in artifacts:
            if artifact in cleaned:
                return ""

        # remove too short or too long
        if len(cleaned) < 2 or len(cleaned) > 50:
            return ""

        # remove if only digits
        if cleaned.isdigit():
            return ""

        return cleaned

    def _is_valid_location(self, location: str) -> bool:
        """Check location validity"""
        if not location or len(location) < 2:
            return False

        location_lower = location.lower()

        # check known locations
        if location_lower in self.priority_locations:
            return True

        # check regional markers
        for markers in self.regional_markers.values():
            if location_lower in [m.lower() for m in markers]:
                return True

        # additional heuristic - contains Georgian or Latin letters
        has_georgian = any(ord(char) >= 0x10A0 and ord(char) <= 0x10FF for char in location)
        has_cyrillic = any(ord(char) >= 0x0400 and ord(char) <= 0x04FF for char in location)
        has_latin = any(char.isalpha() and ord(char) < 256 for char in location)

        return has_georgian or has_cyrillic or has_latin

    def _sort_by_priority(self, locations: List[str]) -> List[str]:
        """Sort locations by priority"""
        if not locations:
            return []

        def priority_score(location: str) -> int:
            location_lower = location.lower()
            if location_lower in self.priority_locations:
                return 100

            for markers in self.regional_markers.values():
                if location_lower in [m.lower() for m in markers]:
                    return 50

            return 1

        return sorted(set(locations), key=priority_score, reverse=True)

    def _determine_region(self, locations: List[str]) -> Optional[str]:
        """Determine region based on locations"""
        if not locations:
            return None

        for location in locations:
            location_lower = location.lower()

            # check regional markers
            for region, markers in self.regional_markers.items():
                if location_lower in [m.lower() for m in markers]:
                    return region

            # check known cities and their regions
            city_to_region = {
                'тбилиси': 'тбилиси',
                'tbilisi': 'тбилиси',
                'мцхета': 'мцхета-мтианети',
                'mtskheta': 'мцхета-мтианети',
                'батуми': 'аджария',
                'batumi': 'аджария',
                'кутаиси': 'имеретия',
                'kutaisi': 'имеретия',
                'сигнахи': 'кахетия',
                'signagi': 'кахетия',
                'telavi': 'кахетия',
                'телави': 'кахетия',
                'гори': 'шида-картли',
                'gori': 'шида-картли',
                'кобулети': 'аджария',
                'kobuleti': 'аджария'
            }

            for city, region in city_to_region.items():
                if city in location_lower:
                    return region

        return None

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Final result normalization"""
        # remove duplicates from all_locations
        result['all_locations'] = list(dict.fromkeys(result['all_locations']))

        # capitalize primary_location
        if result['primary_location'] != 'неизвестно':
            result['primary_location'] = result['primary_location'].title()

        # Rremove empty locations
        result['all_locations'] = [loc for loc in result['all_locations'] if loc and loc.strip()]

        return result