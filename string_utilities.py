roman_map = {
    "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5", "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10",
    "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"
}

def replace_roman_numerals(text):
    for roman, num in roman_map.items():
        if text.endswith(roman):  
            return text[:-len(roman)] + num  # 로마자 제거 후 숫자 추가
    return text

def remove_trailing_numerals(text: str):
    while '0' <= text[-1] <= '9':
        text = text[:-1]
    
    return text