# Unambiguously ENTITY_COUNT
ORGANIZATIONAL_TERMS = {
    r"compan(?:y|ies)",
    r"corporations?",
    r"subsidiar(?:y|ies)",
    r"affiliates?",
    r"airlines?",
    r"unions",
    r"partnerships?",
    r"ventures?",
    r"competitors?",
    r"suppliers?",
    r"customers?",
    r"clients?",
    r"contractors?",
    r"dealers?",
    r"distributors?",
    r"agenc(?:y|ies)",
}

PRODUCT_TERMS = {
    r"products?",
    r"brands?",
    r"lines?",  # product lines
    r"models?",
    r"patents?",
    r"licenses?",
    r"contracts?",
    r"agreements?",
    r"permits?",
    r"deliver(?:y|ies)",
    r"orders?",
    r"suppl(?:y|ies)",
    r"invoices?",
    r"shipments?",
    r"receipts?",
    r"inventor(?:y|ies)",
    r"purchases?",
}

# --- Ambiguous: context decides ---
AMBIGUOUS_TERMS = {
    r"segments?",  
    r"divisions?", 
    r"markets?",
    r"groups?", 
    r"networks?",  
    r"channels?",  
    r"portfolios?",
}
