"""Explicit v0.5 department roles, acceptance checks and routing suggestions."""
import re

WEB_ROLES = {
 'web-application-director':('WD-01','Web & Application Director','Analyze requirements; choose a scoped workflow; coordinate specialists and child tasks; consolidate tested artifacts.','Project requirements, constraints, milestones, risks, technology decisions and deliverables.'),
 'web-technology-researcher':('WD-02','Web Technology Researcher','Research official current framework versions, SDKs, compatibility, security advisories, hosting, databases and authentication.','Dated source URLs, compared versions, compatibility findings, alternatives and UNVERIFIED gaps.'),
 'web-ui-ux-researcher':('WD-03','UI/UX Design Researcher','Research comparable products, typography, color, interaction, responsive layout, accessibility and supported user evidence.','Design brief, licensed references and moodboard specifications; distinguish usability evidence from subjective trends.'),
 'web-product-ux-architect':('WD-04','Product & UX Architect','Translate the request into requirements, user stories, journeys, information architecture and interaction specifications.','Wireframe/page specifications, responsive behavior, accessibility criteria and documented design decisions.'),
 'web-design-system-specialist':('WD-05','UI Design & Design-System Specialist','Develop typography, color, spacing, tokens, reusable components and design handoffs.','Local design specification and code components; edit Figma only through a genuinely capable authorized connector.'),
 'web-frontend-engineer':('WD-06','Frontend Engineer','Implement accessible responsive interfaces, components, client state, API integration and maintainable tests.','Actual frontend files, dependency/stack rationale, run instructions and test evidence.'),
 'web-backend-api-engineer':('WD-07','Backend & API Engineer','Implement input-validated APIs, business logic, authentication/authorization boundaries, database integration and logging.','Actual backend files, API contracts, security assumptions and meaningful tests.'),
 'web-database-architect':('WD-08','Database & Application Architecture Specialist','Design data models, relationships, migrations, retention, performance, backup and data security.','Schema/migration files, rollback procedures and architecture decision records.'),
 'web-mobile-specialist':('WD-09','Mobile Application Specialist','Evaluate native versus cross-platform needs, available SDKs, platform compatibility, app-store constraints and supported implementations.','Mobile design/build plan or actual built artifact; never claim iOS/Android compilation without a successful real build.'),
 'web-testing-accessibility-engineer':('WD-10','Testing & Accessibility Engineer','Run appropriate unit, integration, end-to-end, keyboard, responsive, accessibility and browser compatibility checks.','Internal test evidence and defects; final independent QA approval remains with qa-auditor.'),
 'web-security-performance-engineer':('WD-11','Security & Performance Engineer','Review input/authentication, exposed secrets, dependencies, common vulnerabilities and measured performance.','Scoped findings, evidence, fixes and limitations; no intrusive third-party testing without authorization.'),
 'web-devops-deployment-engineer':('WD-12','DevOps & Deployment Engineer','Prepare reproducible builds, CI/CD, environment configuration, release readiness and rollback.','Build/deployment runbooks and rollback evidence; external deployment needs exact authorization and actual supported access.'),
 'web-documentation-maintenance-specialist':('WD-13','Technical Documentation & Maintenance Specialist','Maintain setup guides, architecture decisions, developer documentation, releases, limitations and lifecycle research.','Documentation, maintenance plan and approved lessons in the Vault.'),
}
SOCIAL_ROLES = {
 'social-media-director':('SM-01','Social Media Director','Define campaign objectives, coordinate specialists and approval deadlines, consolidate original content for QA and evaluate actual results.','Campaign objectives, scoped team, content plan, risks and connector needs.'),
 'social-trends-researcher':('SM-02','Social Media Trends Researcher','Research current platform changes, formats, public trends, keywords, audience interests and competitors.','Dated sources and original-content opportunities; distinguish public observations, account analytics and hypotheses.'),
 'social-audience-competitor-analyst':('SM-03','Audience & Competitor Intelligence Analyst','Research authorized/public audience needs, competitor positioning, content gaps and available engagement evidence.','Audience/persona evidence with assumptions; never imply access to private competitor analytics.'),
 'social-content-strategist':('SM-04','Content Strategist','Define brand-aligned content pillars, platform approaches, series, campaigns and monthly/weekly plans.','Actionable campaign strategy, brief, calendar and success measures.'),
 'social-copywriter-scriptwriter':('SM-05','Copywriter & Scriptwriter','Draft platform-appropriate original captions, posts, hooks, calls to action, carousels, scripts and stories.','Versioned copy and source/claim notes; English, Arabic and Sorani drafts require appropriate linguistic verification.'),
 'social-creative-brand-designer':('SM-06','Creative Director & Brand Designer','Define visual direction, typography, colors, brand guidelines and creative briefs; coordinate supported image tools.','Brand specification, licensed visual references and consistent production direction.'),
 'social-graphic-carousel-specialist':('SM-07','Graphic Design & Carousel Specialist','Prepare legible social graphics, carousel layouts, reusable templates, aspect ratios and platform adaptations.','Real supported local SVG/HTML/design files or explicit handoff specifications; no fictional Figma edits.'),
 'social-video-motion-specialist':('SM-08','AI Video & Motion Production Specialist','Prepare original video concepts, scripts, storyboards, motion, captions/subtitles and supported production assets.','Actual outputs when available, otherwise a production-ready brief; Hyperframes/Higgsfield names do not establish connections.'),
 'social-calendar-scheduling-specialist':('SM-09','Content Calendar & Scheduling Specialist','Plan approval deadlines, publishing cadence and audience timezones; track draft/reviewed/approved/scheduled/published/failed/archived items.','Versioned timezone-aware content calendar; proposed times are hypotheses without actual analytics; no automatic publication.'),
 'social-analytics-specialist':('SM-10','Social Media Analytics Specialist','Analyze authorized/supplied reach, impressions, engagement and campaign outcomes with explicit metric definitions.','Source-linked actual-data reports, missing-value/estimate labels and testable recommendations.'),
 'social-community-reputation-specialist':('SM-11','Community & Reputation Specialist','Research community approaches, draft replies and FAQs, summarize recurring questions and escalate reputation risks.','Draft-only replies, guidelines and sensitive communication escalations; no live messages/moderation without scoped authorization.'),
 'social-platform-integration-specialist':('SM-12','Social Platform Integration Specialist','Discover runtime connectors, supported actions, authentication, permissions, costs/rates, failures and fallback tools.','Evidence-backed capability records and artifact references; never hardcode credentials or assume access from a name.'),
 'social-compliance-content-reviewer':('SM-13','Social Media Compliance & Content Reviewer','Internally review accuracy, brand consistency, platform suitability, readability, captions, copyright and disclosures.','Precise content corrections and evidence; qa-auditor retains independent final approval.'),
}
EXTRA_QA = {
 'web-development':('accessibility','responsive_behavior','performance','maintainability','dependency_compatibility','documentation','deployment_readiness'),
 'social-media':('audience_alignment','brand_consistency','readability','visual_quality','platform_suitability','copyright_licensing','disclosures','calendar_correctness','connector_authorization','analytics_integrity'),
}
NAMESPACE_OWNERS = {
 'web-development':'web-development','web-design-research':'web-development','application-architecture':'web-development',
 'social-media':'social-media','social-trends':'social-media','brand-assets':'social-media',
 'content-calendar':'social-media','social-analytics':'social-media',
}


def routing_suggestion(request):
    """Transparent lexical hints for Management; never silently assigns or invokes."""
    if not isinstance(request,str) or not request.strip():raise ValueError('Routing request is required')
    text=request.casefold();candidates=[]
    patterns={
      'web-development':r'\b(website|web app|application|frontend|backend|api|landing page|accessibility|bug fix|database|mobile app|saas|portfolio)\b',
      'social-media':r'\b(social media|instagram|facebook|tiktok|linkedin|pinterest|youtube|caption|carousel|campaign|content calendar|personal brand|community|tweet)\b',
      'ecommerce':r'\b(iraq|kurdistan|supplier|dropshipping|cash on delivery|commercial feasibility)\b',
      'shorts':r'\b(shorts income|content income|shorts monetization|shorts lab)\b',
      'trading':r'\b(trading|paper trade|broker|stock market)\b',
    }
    for department,pattern in patterns.items():
        matches=sorted(set(re.findall(pattern,text)))
        if matches:candidates.append({'department':department,'matched_terms':matches})
    return {'suggestions':candidates,'default_if_ambiguous':'management','invoked_agents':[],
        'note':'Management must confirm scope and requested owner; use scoped child tasks for collaboration. General social content is independent of Income Shorts.'}
