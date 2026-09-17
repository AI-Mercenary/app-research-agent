"""
The 100 target apps for the Composio AI Product Ops take-home, grouped by the
exact 10 categories given in the assignment. Category is used later for
pattern analysis (e.g. "CRM apps are mostly gated behind paid plans").
"""

APPS = {
    "CRM and Sales": [
        "Salesforce", "HubSpot", "Pipedrive", "Attio", "Twenty",
        "Podio", "Zoho CRM", "Close", "Copper", "DealCloud",
    ],
    "Support and Helpdesk": [
        "Zendesk", "Intercom", "Freshdesk", "Front", "Pylon",
        "LiveAgent", "Plain", "Help Scout", "Gorgias", "Gladly",
    ],
    "Communications and Messaging": [
        "Slack", "Twilio", "Zoho Cliq", "Lark (Larksuite)", "Pumble",
        "Discord", "Telegram", "WhatsApp Business", "Aircall", "Vonage",
    ],
    "Marketing, Ads, Email and Social": [
        "Google Ads", "Meta Ads", "LinkedIn Ads", "GoHighLevel", "Mailchimp",
        "Klaviyo", "systeme.io", "Pinterest", "Threads (Meta)", "SendGrid",
    ],
    "Ecommerce": [
        "Shopify", "WooCommerce", "BigCommerce", "Salesforce Commerce Cloud", "Magento (Adobe Commerce)",
        "Squarespace", "Ecwid", "Gumroad", "Amazon Selling Partner", "fanbasis",
    ],
    "Data, SEO and Scraping": [
        "DataForSEO", "SE Ranking", "Ahrefs", "MrScraper", "Apify",
        "Firecrawl", "Bright Data", "Sherlock", "Waterfall.io", "Clay",
    ],
    "Developer, Infra and Data platforms": [
        "GitHub", "Vercel", "Netlify", "Cloudflare", "Supabase",
        "Neo4j", "Snowflake", "MongoDB Atlas", "Datadog", "Sentry",
    ],
    "Productivity and Project Management": [
        "Notion", "Airtable", "Linear", "Jira", "Asana",
        "Monday.com", "ClickUp", "Coda", "Smartsheet", "Harvest",
    ],
    "Finance and Fintech": [
        "Stripe", "Plaid", "Binance", "Paygent Connect", "iPayX",
        "QuickBooks", "Xero", "Brex", "Ramp", "PitchBook",
    ],
    "AI, Research and Media-native": [
        "NotebookLM", "Otter AI", "Fathom", "Consensus", "Reducto",
        "Devin", "higgsfield", "Mermaid CLI", "YouTube Transcript", "Grain",
    ],
}

def flat_list():
    """Returns [(app_name, category), ...] for all 100 apps."""
    out = []
    for category, apps in APPS.items():
        for app in apps:
            out.append((app, category))
    return out
