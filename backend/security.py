"""
Security Module — Clinical Graph System (Simplified)
─────────────────────────────────────────────────────
2 katman:
  1. Mapper filtresi → Sadece dictionary'de eşleşen terimler graph'a girer
  2. Cypher sanitize → Raw text alanları (ilaç, oral intake vb.) temizlenir

Parametreli sorgular ($param) zaten Cypher injection'ın %99'unu engeller.
Bu modül ekstra savunma hattı olarak raw string'leri temizler.
"""

import re


def sanitize_text(text: str) -> str:
    """
    Raw text alanlarını Neo4j'e yazmadan önce temizle.
    Cypher syntax karakterlerini ve tehlikeli pattern'leri çıkarır.
    """
    if not text:
        return ""

    # Cypher özel karakterleri temizle
    sanitized = re.sub(r'[{}\[\]`\\;]', '', text)

    # Yorum injection'larını temizle
    sanitized = re.sub(r'(--|//|/\*|\*/)', '', sanitized)

    # Çoklu boşluk ve satır sonu
    sanitized = re.sub(r'\s+', ' ', sanitized)

    return sanitized.strip()


def check_dangerous_input(text: str) -> tuple[bool, str]:
    """
    Açıkça zararlı input kontrolü.
    Sadece kesin tehlikeli pattern'leri yakalar — normal tıbbi metni engellemez.
    Returns: (is_dangerous, reason)
    """
    if not text:
        return False, ""

    # Cypher DDL/DML komutları (büyük/küçük harf duyarsız)
    cypher_patterns = [
        (r'\bCREATE\s+\(', "CREATE node"),
        (r'\bDROP\s+', "DROP command"),
        (r'\bDETACH\s+DELETE\b', "DETACH DELETE"),
        (r'\bLOAD\s+CSV\b', "LOAD CSV"),
        (r'\bCALL\s+db\.', "db function call"),
        (r'\bCALL\s+apoc\.', "apoc function call"),
        (r'\bMATCH\s*\(', "MATCH query"),
        (r'\bRETURN\s+\w', "RETURN clause"),
        (r'--\s*\w', "comment injection"),
        (r'//\s*\w', "comment injection"),
        (r'\bSET\s+\w+\s*=', "SET property"),
        (r'\bREMOVE\s+\w', "REMOVE command"),
        (r'\bMERGE\s*\(', "MERGE node"),
    ]

    # Script injection
    script_patterns = [
        (r'<script', "script tag"),
        (r'javascript:', "javascript URI"),
        (r'onerror\s*=', "event handler injection"),
        (r'onload\s*=', "event handler injection"),
    ]

    for pattern, reason in cypher_patterns + script_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True, reason

    return False, ""


def validate_form(form_data: dict) -> tuple[bool, list[str]]:
    """
    Tüm form alanlarını kontrol et.
    Returns: (is_valid, reasons)
    """
    reasons = []
    for key, value in form_data.items():
        if not isinstance(value, str) or not value.strip():
            continue
        is_dangerous, reason = check_dangerous_input(value)
        if is_dangerous:
            reasons.append(f"[{key}]: {reason}")

    return len(reasons) == 0, reasons
