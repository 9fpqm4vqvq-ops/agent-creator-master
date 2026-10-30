"""Explicit agent allowlist and department hierarchy; no downloaded role auto-activation."""
ROLES = {
    'master-agent': ('management', None, 'maos'),
    'agent-creator-researcher': ('agent-development', 'master-agent', 'maos'),
    'income-director': ('income', 'master-agent', 'income'),
    'trading-director': ('trading', 'income-director', 'day-trader'),
    'shorts-director': ('shorts', 'income-director', 'shorts'),
    'qa-auditor': ('quality', 'master-agent', 'maos'),
}
# Known imported roles are explicitly registered; arbitrary downloaded files do not
# become active agents just by appearing on disk.
for name in ('agent-runner', 'task-router', 'agent-creator', 'token-watchdog',
             'research-analyst', 'rework-specialist', 'registry-manager',
             'learning-analyst', 'reporting-specialist'):
    ROLES[name] = ('management', 'master-agent', 'maos')
for name in ('reporting-learning-agent', 'creative-opportunity-generator',
             'rework-improvement-agent', 'experiment-validation-agent',
             'data-profitability-analyst', 'business-execution-planner',
             'quality-fraud-auditor', 'market-competitor-analyst',
             'global-opportunity-researcher', 'continuous-monitoring-agent',
             'iraq-feasibility-researcher'):
    ROLES['ioi-' + name] = ('income', 'income-director', 'income')
for name in ('quality-check-compliance', 'analytics-optimization', 'visual-video-producer',
             'scriptwriter-storyteller', 'content-strategist',
             'competitor-intelligence-analyst', 'niche-market-researcher'):
    ROLES['shorts-' + name] = ('shorts', 'shorts-director', 'shorts')
DOMAINS = {'management': 'master-agent', 'agent-development': 'agent-creator-researcher',
           'income': 'income-director', 'trading': 'trading-director',
           'shorts': 'shorts-director', 'quality': 'qa-auditor'}


# v0.3 management is a real department lead; preserve all existing role names.
ROLES['management-director'] = ('management', 'master-agent', 'maos')
for name, (department, parent, bundle) in list(ROLES.items()):
    if parent == 'master-agent' and name not in {'management-director', 'qa-auditor'}:
        ROLES[name] = (department, 'management-director', bundle)
for name in ('iraq-ecommerce-director', 'iraq-market-researcher',
             'product-opportunity-researcher', 'supplier-dropshipping-researcher',
             'logistics-fulfillment-analyst', 'ecommerce-finance-payments-analyst',
             'ecommerce-marketing-strategist', 'ecommerce-business-validation-analyst'):
    ROLES[name] = ('ecommerce', 'income-director' if name == 'iraq-ecommerce-director'
                   else 'iraq-ecommerce-director', 'income')
DOMAINS['management'] = 'management-director'
DOMAINS['ecommerce'] = 'iraq-ecommerce-director'
ROLES['agent-creator'] = ('agent-development', 'agent-creator-researcher', 'maos')
NAMESPACES = {'management', 'income', 'ecommerce', 'trading', 'shorts', 'research', 'quality', 'shared'}
DEPARTMENT_NAMESPACE = {'agent-development': 'research'}

ROLES['department-health-auditor'] = ('agent-development', 'agent-creator-researcher', 'maos')
ROLES['knowledge-freshness-auditor'] = ('agent-development', 'agent-creator-researcher', 'maos')
