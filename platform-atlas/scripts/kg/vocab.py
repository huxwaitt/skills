"""Fixed entity and relation types for the platform knowledge graph.

Every fact uses one of these. Facts between two entities use a link type; facts about one entity
(a status, a limit, an endpoint, a setup step) use a HAS_* type with no target. The free `fact`
sentence carries the detail, so the list stays short. Facts about one entity are compared per
relation type, so a newer status, limit or version replaces the older one.
"""

ENTITY_TYPES = {
    "Platform": "a vendor platform or suite as a whole (AWS, Snowflake, Microsoft 365 Copilot)",
    "Service": "a product or managed service on a platform (Amazon Bedrock, Cortex Agents, Copilot Studio)",
    "Feature": "a named capability inside a service (Bedrock Guardrails, AgentCore Gateway, Genie Conversation API)",
    "Model": "an AI model or model family offered on a platform",
    "API": "an HTTP, SQL or RPC interface (Responses API, Snowflake SQL API, EPM REST API)",
    "SDK": "a client library or agent framework package",
    "CLI": "a command-line tool",
    "MCPServer": "a Model Context Protocol server, local or remote",
    "Connector": "a prebuilt integration, connector or driver between systems",
    "Protocol": "a standard or protocol (MCP, A2A, OAuth 2.0, SAML, SCIM, OpenAPI)",
    "AuthMethod": "a way to authenticate (service principal, key pair, PAT, workload identity federation)",
    "Role": "a built-in or typical role (Azure AI User, ACCOUNTADMIN, Service Administrator)",
    "Permission": "a permission, privilege, policy statement, scope or grant",
    "License": "a license, edition, SKU, tier or billing unit",
    "Organization": "a company or vendor",
    "Other": "anything else",
}

LINKS = {
    "PART_OF": "something (source) is a component, feature, edition or sub-product of something larger (target)",
    "PROVIDED_BY": "a service, model, tool or offering (source) is made or sold by a vendor or platform (target)",
    "AVAILABLE_ON": "a model, service or tool (source) can be used through another platform or service (target)",
    "EXPOSES": "a service (source) offers an API, MCP server, CLI command group, SDK or endpoint (target)",
    "AUTHENTICATES_WITH": "a service, API, CLI, connector or agent (source) accepts or uses an authentication method (target)",
    "REQUIRES_ROLE": "doing something with a service or feature (source) needs a role (target); the sentence says for what",
    "REQUIRES_PERMISSION": "doing something with a service or feature (source) needs a permission, privilege or policy (target)",
    "REQUIRES_LICENSE": "a service or feature (source) needs a license, edition or SKU (target)",
    "GRANTS": "a role (source) grants a permission or access to a service (target)",
    "ADMINISTERED_BY": "a setting, service or approval (source) is controlled by an admin role (target)",
    "SUPPORTS": "a service or tool (source) supports a protocol, model, language, format or pattern (target)",
    "INTEGRATES_WITH": "a service or connector (source) connects to, calls or is called by another system (target)",
    "MANAGES": "a CLI, SDK or IaC tool (source) creates or administers a service or resource (target)",
    "DEPENDS_ON": "something (source) needs or is blocked by something else (target)",
    "REPLACED": "something (source) replaces, supersedes or is the new name of something older (target)",
    "ALTERNATIVE_TO": "something (source) is an alternative or competitor to something else (target) for the same job",
    "RELATED_TO": "any other link between two entities; use only when nothing above fits",
}

ATTRIBUTES = {
    "HAS_STATUS": "release status: GA, preview, beta, deprecated, retired; put the date in the sentence",
    "HAS_DATE": "when something launched, changed, will be deprecated or retired",
    "HAS_CAPABILITY": "something the entity can do",
    "HAS_LIMIT": "a quota, rate limit, size limit, timeout or maintenance window",
    "HAS_PRICING": "how it is billed, the unit, and a price with the date it was shown",
    "HAS_REGION": "where it is available or where data is processed and stored",
    "HAS_SETUP_STEP": "a step to get access or configure it (sign-up, enablement, admin approval)",
    "HAS_ENDPOINT": "a URL, base path, package name, install command or config file location",
    "HAS_COMMAND": "a CLI command that matters for agent work, with what it does",
    "HAS_VERSION": "a current version number",
    "HAS_SECURITY": "a security, network isolation, data-usage, residency or compliance property",
    "HAS_GOTCHA": "a pitfall, common failure, surprising behaviour or known gap",
    "HAS_DOC": "a documentation, reference, llms.txt, changelog or status page URL",
    "HAS_DESCRIPTION": "what the entity is, its purpose or definition, or any other detail",
}

ALL = {**LINKS, **ATTRIBUTES}
DEFAULT_LINK = "RELATED_TO"
DEFAULT_ATTRIBUTE = "HAS_DESCRIPTION"

# When a link type is used without a target, the one-entity type that keeps its meaning.
LINK_AS_ATTRIBUTE = {"REQUIRES_ROLE": "HAS_SETUP_STEP", "REQUIRES_PERMISSION": "HAS_SETUP_STEP",
                     "REQUIRES_LICENSE": "HAS_PRICING", "AUTHENTICATES_WITH": "HAS_SECURITY",
                     "EXPOSES": "HAS_ENDPOINT", "SUPPORTS": "HAS_CAPABILITY", "DEPENDS_ON": "HAS_SETUP_STEP",
                     "REPLACED": "HAS_STATUS", "AVAILABLE_ON": "HAS_REGION"}

# Off-list names extraction agents drift to, mapped (link type, one-entity type).
_ALIASES = {
    "STATUS": (None, "HAS_STATUS"), "RELEASE_STATUS": (None, "HAS_STATUS"), "DEPRECATED": ("REPLACED", "HAS_STATUS"),
    "DATE": (None, "HAS_DATE"), "LAUNCHED": (None, "HAS_DATE"), "RELEASED": (None, "HAS_DATE"),
    "CAPABILITY": (None, "HAS_CAPABILITY"), "HAS_FEATURE": ("PART_OF", "HAS_CAPABILITY"), "FEATURE": ("PART_OF", "HAS_CAPABILITY"),
    "LIMIT": (None, "HAS_LIMIT"), "QUOTA": (None, "HAS_LIMIT"), "HAS_QUOTA": (None, "HAS_LIMIT"), "RATE_LIMIT": (None, "HAS_LIMIT"),
    "PRICING": (None, "HAS_PRICING"), "PRICE": (None, "HAS_PRICING"), "HAS_PRICE": (None, "HAS_PRICING"),
    "BILLED_BY": ("REQUIRES_LICENSE", "HAS_PRICING"), "LICENSED_BY": ("REQUIRES_LICENSE", "HAS_PRICING"),
    "REGION": (None, "HAS_REGION"), "AVAILABLE_IN": (None, "HAS_REGION"), "HAS_AVAILABILITY": (None, "HAS_REGION"),
    "SETUP": (None, "HAS_SETUP_STEP"), "SETUP_STEP": (None, "HAS_SETUP_STEP"), "HAS_PREREQUISITE": ("DEPENDS_ON", "HAS_SETUP_STEP"),
    "REQUIRES": ("DEPENDS_ON", "HAS_SETUP_STEP"), "PREREQUISITE": ("DEPENDS_ON", "HAS_SETUP_STEP"),
    "ENDPOINT": (None, "HAS_ENDPOINT"), "HAS_URL": (None, "HAS_ENDPOINT"), "URL": (None, "HAS_ENDPOINT"),
    "INSTALL": (None, "HAS_ENDPOINT"), "HAS_INSTALL": (None, "HAS_ENDPOINT"), "HAS_PACKAGE": (None, "HAS_ENDPOINT"),
    "COMMAND": (None, "HAS_COMMAND"), "HAS_CLI_COMMAND": (None, "HAS_COMMAND"),
    "VERSION": (None, "HAS_VERSION"), "SECURITY": (None, "HAS_SECURITY"), "HAS_COMPLIANCE": (None, "HAS_SECURITY"),
    "HAS_DATA_RESIDENCY": (None, "HAS_REGION"), "HAS_GOVERNANCE": (None, "HAS_SECURITY"),
    "GOTCHA": (None, "HAS_GOTCHA"), "HAS_PITFALL": (None, "HAS_GOTCHA"), "HAS_RISK": (None, "HAS_GOTCHA"),
    "HAS_ISSUE": (None, "HAS_GOTCHA"), "HAS_RULE": (None, "HAS_SECURITY"), "HAS_CONSTRAINT": (None, "HAS_LIMIT"),
    "DOC": (None, "HAS_DOC"), "HAS_DOCS": (None, "HAS_DOC"), "HAS_DOCUMENTATION": (None, "HAS_DOC"), "DOCUMENTED_AT": (None, "HAS_DOC"),
    "INCLUDES": ("PART_OF", "HAS_CAPABILITY"), "HAS_COMPONENT": ("PART_OF", "HAS_CAPABILITY"), "COMPONENT_OF": ("PART_OF", None),
    "OFFERED_BY": ("PROVIDED_BY", None), "MADE_BY": ("PROVIDED_BY", None), "SOLD_BY": ("PROVIDED_BY", None),
    "HOSTS": ("AVAILABLE_ON", None), "HOSTED_ON": ("AVAILABLE_ON", None), "RUNS_ON": ("AVAILABLE_ON", None),
    "PROVIDES": ("EXPOSES", "HAS_CAPABILITY"), "OFFERS": ("EXPOSES", "HAS_CAPABILITY"), "HAS_API": ("EXPOSES", "HAS_ENDPOINT"),
    "USES_AUTH": ("AUTHENTICATES_WITH", "HAS_SECURITY"), "AUTHENTICATED_BY": ("AUTHENTICATES_WITH", None),
    "USES": ("INTEGRATES_WITH", None), "CONNECTS_TO": ("INTEGRATES_WITH", None), "CALLS": ("INTEGRATES_WITH", None),
    "REQUIRES_PRIVILEGE": ("REQUIRES_PERMISSION", "HAS_SETUP_STEP"), "NEEDS_ROLE": ("REQUIRES_ROLE", "HAS_SETUP_STEP"),
    "MANAGED_BY": ("ADMINISTERED_BY", None), "CONTROLLED_BY": ("ADMINISTERED_BY", None),
    "SUPERSEDES": ("REPLACED", None), "RENAMED_FROM": ("REPLACED", None), "REPLACES": ("REPLACED", None),
    "SUCCESSOR_OF": ("REPLACED", None), "COMPETES_WITH": ("ALTERNATIVE_TO", None),
}


def canonical(relation, has_target):
    """Return (valid relation type, whether the original was already on the list).

    Off-list names are mapped through known aliases ("QUOTA" -> HAS_LIMIT, "HOSTED_ON" -> AVAILABLE_ON),
    then "HAS_" + name, then the defaults, so a drifting agent still lands facts where the replaced-fact
    check compares them."""
    r = (relation or "").strip().upper().replace(" ", "_").replace("-", "_")
    if has_target and r in LINKS:
        return r, True
    if not has_target and r in ATTRIBUTES:
        return r, True
    link, attr = _ALIASES.get(r, (None, None))
    if has_target:
        if link in LINKS:
            return link, False
        return DEFAULT_LINK, False
    if attr in ATTRIBUTES:
        return attr, False
    if "HAS_" + r in ATTRIBUTES:
        return "HAS_" + r, False
    if r in LINK_AS_ATTRIBUTE or link in LINK_AS_ATTRIBUTE:
        return LINK_AS_ATTRIBUTE.get(r) or LINK_AS_ATTRIBUTE[link], False
    return DEFAULT_ATTRIBUTE, False


def prompt_table():
    lines = ["Entity types:"]
    lines += [f"- `{k}`: {v}" for k, v in ENTITY_TYPES.items()]
    lines += ["", "Links between two entities (`target` is an entity):"]
    lines += [f"- `{k}`: {v}" for k, v in LINKS.items()]
    lines += ["", "Facts about one entity (`target` is null):"]
    lines += [f"- `{k}`: {v}" for k, v in ATTRIBUTES.items()]
    return "\n".join(lines)
