#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unicode utilities for Vietnamese text processing
"""

import unicodedata

def remove_vietnamese_accents(text: str) -> str:
    """
    Remove Vietnamese accents from text for fuzzy matching
    
    Examples:
        "Phở" → "Pho"
        "Bánh Mì" → "Banh Mi"
        "Bún Chả" → "Bun Cha"
    """
    if not text:
        return text
    # Normalize to NFD (decomposed form)
    nfd = unicodedata.normalize('NFD', text)
    
    # Remove combining characters (accents)
    without_accents = ''.join(
        char for char in nfd
        if unicodedata.category(char) != 'Mn'
    )
    
    # Handle special Vietnamese characters
    replacements = {
        'đ': 'd',
        'Đ': 'D',
    }
    
    for viet_char, latin_char in replacements.items():
        without_accents = without_accents.replace(viet_char, latin_char)
    
    return without_accents


def normalize_for_search(text: str) -> str:
    """
    Normalize text for search comparison
    - Remove accents
    - Lowercase
    - Strip whitespace
    """
    if not text:
        return text
    
    text = remove_vietnamese_accents(text)
    text = text.lower().strip()
    return text


# Test
if __name__ == "__main__":
    test_cases = [
        "Phở",
        "Bánh Mì",
        "Bún Chả",
        "Cơm Tấm",
        "Gỏi Cuốn",
        "Chả Giò",
    ]
    
    print("=" * 60)
    print("TEST VIETNAMESE ACCENT REMOVAL")
    print("=" * 60)
    
    for text in test_cases:
        no_accent = remove_vietnamese_accents(text)
        normalized = normalize_for_search(text)
        print(f"\n'{text}'")
        print(f"  → No accents: '{no_accent}'")
        print(f"  → Normalized: '{normalized}'")
