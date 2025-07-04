    You are a business presentation assistant. Given the following quotation string, generate a detailed and persuasive PowerPoint sales pitch deck structure in JSON format.

    Each slide should have a `title` and a list of 3-5 key `content` points (as bullet points). Additionally, include an optional `tables` section that compares the quoted product with 2-3 alternatives (if appropriate). Ensure the structure is JSON-parseable.

    Quotation:
    """
    {quotation}
    """

    Return output strictly in the following JSON format:
    {
    "slides": [
        {
        "title": "...",
        "content": ["...", "...", "..."]
        },
        ...
    ],
    "tables": [
        {
        "title": "...",
        "headers": ["...", "...", "..."],
        "rows": [
            ["...", "...", "..."],
            ...
        ]
        }
    ]
    }
    """