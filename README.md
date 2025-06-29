# AI Ads Advisor (AdVizeAi)

⸻

AI Ads Advisor (AdsAi) is a modern SaaS platform that helps media buyers and e-commerce marketers optimize their Meta (Facebook, Instagram), TikTok, and Snapchat ad campaigns using AI. It offers real-time performance tracking, campaign optimization suggestions, and a smart assistant to answer ad-related questions.

⸻

Why AdvizeAi?

⸻

Running paid ads is complex. Managing multiple platforms, analyzing thousands of metrics, and making fast decisions is time-consuming. AdsAi solves this by:
- Connecting your ad accounts in one dashboard
- Providing real-time campaign performance data
- Recommending AI-generated optimization strategies
- Offering a conversational AI assistant tailored to marketers

⸻

Screenshots (Coming Soon)

⸻

Live Demo

⸻

Tech Stack

| Layer        | Technologies |
|--------------|--------------|
| Frontend     | React, TypeScript, Tailwind CSS, shadcn/ui, lucide-react |
| Backend      | FastAPI (Python), OAuth, REST APIs |
| AI Layer     | RAG (Retrieval-Augmented Generation) |
| Auth         | Google OAuth, Facebook Login |
| Routing      | React Router |
| Dev Tools    | Vite, Prettier, ESLint |

⸻

Folder Structure

bash
advize-ai/
├── frontend/               # React app
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Route-based views (Login, Dashboard, etc.)
│   │   ├── routes/         # React Router setup
│   │   ├── lib/            # Utility functions, API handlers
│   └── public/
│
├── backend/                # FastAPI app
│   ├── app/
│   │   ├── api/            # Routes and endpoints
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # Business logic, integrations
│   │   └── auth/           # OAuth2 and JWT
│   └── main.py             # App entry point
│
├── .env.example            # Example environment variables
└── README.md


⸻

🔧 Getting Started

1. Clone the Repository

git clone https://github.com/zoncagit/advize-ai

2. Environment Variables



⸻

Running the Project Locally



⸻

Features
 • Secure OAuth login (Google, Facebook)
 • Dashboard with real-time ad campaign metrics
 • AI-generated optimization suggestions
 • Chat interface to ask marketing questions
 • Connect/Disconnect ad accounts (Meta, TikTok, Snapchat)
 • Notification preferences and settings

⸻

Pages Overview

Page Description
/login Email/password + OAuth login
/connect Connect ad accounts with status indicators
/dashboard Main dashboard showing campaign metrics
/optimize AI suggestions for campaign improvement
/ask-ai Chat-based AI assistant
/settings Manage accounts & preferences


⸻

Design System
 • UI Framework: Tailwind CSS + shadcn/ui
 • Icons: Lucide React
 • Colors: Soft SaaS palette (blues, purples, grays)
 • Typography: Inter or Open Sans

⸻

Dummy Data & APIs

For development, mock data and dummy campaign stats are used. Replace them with real API calls after configuring access to Meta, TikTok, and Snapchat ad platforms.

⸻

Contributing

We welcome contributions!


⸻

Contact

For questions, suggestions, or partnerships:
 • Project Team: الجمعية
 • Email: contact@advizeai.com
 • Website: advizeai.com