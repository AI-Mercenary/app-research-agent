"""
The 100 target apps, grouped by category. Category is used later for
pattern analysis (e.g. "finance apps are mostly gated behind paid plans").
"""

APPS = {
    "Communication": [
        "Slack", "Microsoft Teams", "Discord", "Zoom", "Twilio",
        "SendGrid", "Mailgun", "Telegram", "WhatsApp Business", "RingCentral",
    ],
    "Productivity": [
        "Notion", "Asana", "Trello", "Monday.com", "ClickUp",
        "Airtable", "Todoist", "Basecamp", "Confluence", "Coda",
    ],
    "Developer Tools": [
        "GitHub", "GitLab", "Bitbucket", "Jira", "Linear",
        "CircleCI", "Vercel", "Netlify", "Sentry", "PagerDuty",
    ],
    "CRM & Sales": [
        "Salesforce", "HubSpot", "Pipedrive", "Zoho CRM", "Close",
        "Copper", "Freshsales", "ActiveCampaign", "Intercom", "Zendesk",
    ],
    "Finance & Payments": [
        "Stripe", "PayPal", "Plaid", "QuickBooks", "Xero",
        "Square", "Brex", "Ramp", "Wise", "Adyen",
    ],
    "Marketing": [
        "Mailchimp", "Klaviyo", "Google Ads", "Facebook Ads", "Twitter/X Ads",
        "Hootsuite", "Buffer", "Segment", "Braze", "Customer.io",
    ],
    "Cloud & Infra": [
        "AWS", "Google Cloud Platform", "Microsoft Azure", "Cloudflare", "DigitalOcean",
        "Heroku", "Snowflake", "Databricks", "MongoDB Atlas", "Supabase",
    ],
    "E-commerce": [
        "Shopify", "WooCommerce", "BigCommerce", "Magento", "Etsy",
        "Amazon Seller Central", "eBay", "Wix", "Squarespace", "Printful",
    ],
    "HR & People": [
        "Workday", "BambooHR", "Gusto", "Greenhouse", "Lever",
        "Rippling", "Deel", "ADP", "Namely", "Personio",
    ],
    "Productivity Suites & Storage": [
        "Google Workspace", "Microsoft 365", "Dropbox", "Box", "OneDrive",
        "Calendly", "DocuSign", "Miro", "Figma", "Loom",
    ],
}

def flat_list():
    """Returns [(app_name, category), ...] for all 100 apps."""
    out = []
    for category, apps in APPS.items():
        for app in apps:
            out.append((app, category))
    return out
