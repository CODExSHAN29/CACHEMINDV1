#!/usr/bin/env python3
"""
Generate a realistic 1,000-query customer support workload for CacheMind benchmarking.
Each query follows the format: {"messages": [{"role": "user", "content": "<query>"}], "model": "gpt-4o", "temperature": 0.0}
"""

import json
from pathlib import Path

# Realistic customer support query templates
TEMPLATES = [
    # Account & Billing
    "How do I update my credit card on file?",
    "I need to change my billing address.",
    "Why was I charged twice this month?",
    "Can you help me reset my account password?",
    "I want to cancel my subscription.",
    "How do I upgrade my plan to premium?",
    "What payment methods do you accept?",
    "I received an incorrect invoice, can you review it?",
    "How do I view my payment history?",
    "My account is locked, how do I unlock it?",

    # Technical Support
    "I'm getting a 500 error when trying to upload files.",
    "The API is returning timeout errors, what should I do?",
    "How do I integrate your service with my existing CRM?",
    "I need help setting up webhook notifications.",
    "Why are my requests being rate limited?",
    "How do I enable two-factor authentication?",
    "I'm experiencing slow response times from the API.",
    "Can you help me troubleshoot SSL certificate issues?",
    "How do I configure custom domains for my account?",
    "The dashboard is not loading properly, what's wrong?",

    # Product Information
    "What features are included in the enterprise plan?",
    "How does your data retention policy work?",
    "Can I export my data in CSV format?",
    "What integrations do you currently support?",
    "Is there a mobile app available for your service?",
    "How does your service handle GDPR compliance?",
    "What SLA guarantees do you provide?",
    "Can I customize the branding in my customer portal?",
    "How do I set up automated backups?",
    "What security certifications do you have?",

    # Getting Started
    "How do I create my first project?",
    "What's the difference between trial and paid accounts?",
    "How do I invite team members to my organization?",
    "Where can I find your API documentation?",
    "Do you offer training or onboarding sessions?",
    "How do I migrate from another service to yours?",
    "What are the system requirements for using your API?",
    "How do I enable audit logging for my account?",
    "Can I use custom scripts with your platform?",
    "What's the best way to structure my data for optimal performance?",

    # Feature Requests
    "Can you add support for webhooks in the free tier?",
    "I'd like to request a new integration with Salesforce.",
    "Is it possible to add custom fields to user profiles?",
    "Can you implement bulk user import functionality?",
    "Would you consider adding real-time analytics dashboard?",
    "I need a feature to schedule automated reports.",
    "Can you add support for multi-language interfaces?",
    "Is there a way to customize notification templates?",
    "Can you add more granular permission controls?",
    "I'd like to request a dark mode for the dashboard.",

    # Troubleshooting Specific Errors
    "I keep getting 'Invalid API key' errors even though I just regenerated it.",
    "Why am I seeing 'Resource not found' errors for existing endpoints?",
    "How do I fix 'Authentication failed' errors when using SDK?",
    "What does 'Quota exceeded' mean and how do I resolve it?",
    "I'm getting 'Connection reset by peer' errors intermittently.",
    "Why are my webhook deliveries failing with signature verification errors?",
    "How do I troubleshoot 'Database connection timeout' errors?",
    "What causes 'Template rendering failed' errors in email notifications?",
    "I'm seeing 'Service unavailable' errors during peak hours.",
    "How do I fix 'Malformed JSON' errors in my API requests?",

    # General Questions
    "What are your business hours for customer support?",
    "How do I provide feedback about your service?",
    "Do you offer discounts for non-profit organizations?",
    "Can I get a refund if I'm not satisfied with the service?",
    "How do I delete my account permanently?",
    "What happens to my data if I cancel my subscription?",
    "Do you have a referral program for existing customers?",
    "How often do you release new features or updates?",
    "Can I get a signed copy of your security whitepaper?",
    "What's the process for requesting a custom feature development?"
]

def generate_variations(template: str, count: int) -> list:
    """Generate variations of a template to avoid exact duplicates."""
    variations = []
    for i in range(count):
        if i == 0:
            variations.append(template)
        else:
            # Add slight variations: punctuation, wording, context
            import random
            variants = [
                template,
                template.replace("?", ".") + " Please help.",
                "Could you please help me with: " + template.lower(),
                template + " I'm having trouble with this.",
                "Urgent: " + template,
                template.replace("how", "What is the best way to"),
                template.replace("can you", "Is it possible to"),
                "I need assistance with: " + template,
                template + " This is important for my business.",
                "Please advise on: " + template
            ]
            variations.append(random.choice(variants))
    return variations

def main():
    output_path = Path("benchmarks/workloads/customer_support_1000.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # We need 1000 queries total
    queries_per_template = 1000 // len(TEMPLATES)  # 1000/25 = 40 each
    remainder = 1000 % len(TEMPLATES)  # 0

    all_queries = []
    for template in TEMPLATES:
        variations = generate_variations(template, queries_per_template)
        all_queries.extend(variations)

    # Add remaining queries if any
    if remainder > 0:
        for i in range(remainder):
            all_queries.append(generate_variations(TEMPLATES[i], 1)[0])

    # Shuffle to distribute evenly
    import random
    random.shuffle(all_queries)

    # Write to JSONL file
    with open(output_path, 'w', encoding='utf-8') as f:
        for query in all_queries[:1000]:  # Ensure exactly 1000
            record = {
                "messages": [{"role": "user", "content": query}],
                "model": "gpt-4o",
                "temperature": 0.0
            }
            f.write(json.dumps(record) + "\n")

    print(f"[+] Generated {len(all_queries[:1000])} customer support queries at: {output_path}")

if __name__ == "__main__":
    main()