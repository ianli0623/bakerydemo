import re
from collections.abc import Iterator, Mapping
from dataclasses import replace
from types import MappingProxyType

from .schema import (
    BlockImport,
    HomeImport,
    ImportPlan,
    PageImport,
    SiteSettingsImport,
    SourceLink,
)

ENGLISH_CATALOG = MappingProxyType(
    {
        # Homepage and global content
        "home.title": "SEMI E187 Semiconductor Equipment Cybersecurity Standard and Certification Scheme",
        "home.seo_title": "Home | SEMI E187 Semiconductor Equipment Cybersecurity Standard and Certification Scheme",
        "home.search_description": "Jointly promoted by the Administration for Digital Industries (ADI), MODA, and SEMI, this public-private initiative standardizes cybersecurity across supply chains and highlights Taiwan's role in global supply-chain security governance.",
        "home.hero_badge": "STANDARD AWARENESS × TECHNICAL RESOURCES × CERTIFICATION & COMPLIANCE",
        "home.hero_text": "Jointly promoted by the Administration for Digital Industries (ADI), MODA, and SEMI, this public-private initiative standardizes cybersecurity across supply chains and highlights Taiwan's role in global supply-chain security governance.",
        "home.hero_cta": "Learn About the Certification Process",
        "home.secondary_hero_cta": "Certified Equipment List",
        "home.body.0.value.heading": "Latest News",
        "home.body.0.value.cards.0.eyebrow": "Latest News",
        "home.body.0.value.cards.0.title": "[Official Document] General Rules for the SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme Officially Released",
        "home.body.0.value.cards.0.summary": "[Official Document] General Rules for the SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme Officially Released",
        "home.body.0.value.cards.0.link.label": "2026-04-15 [Official Document] General Rules for the SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme Officially Released",
        "home.body.0.value.cards.1.eyebrow": "Latest News",
        "home.body.0.value.cards.1.title": "[Official Announcement] SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "home.body.0.value.cards.1.summary": "[Official Announcement] SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "home.body.0.value.cards.1.link.label": "2026-03-23 [Official Announcement] SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "home.body.1.value.eyebrow": "EXPLORE THE SITE",
        "home.body.1.value.heading": "Explore by Topic",
        "home.body.1.value.introduction": "Explore the standard, implementation resources, certification process, and industry case studies.",
        "home.body.1.value.cards.0.eyebrow": "Visit Section",
        "home.body.1.value.cards.0.title": "About the Standard",
        "home.body.1.value.cards.0.summary": "Understand the four key domains.",
        "home.body.1.value.cards.0.link.label": "01 About the Standard Understand the four key domains. Visit Section",
        "home.body.1.value.cards.1.eyebrow": "Visit Section",
        "home.body.1.value.cards.1.title": "Implementation Resources",
        "home.body.1.value.cards.1.summary": "Access core documents.",
        "home.body.1.value.cards.1.link.label": "02 Implementation Resources Access core documents. Visit Section",
        "home.body.1.value.cards.2.eyebrow": "Visit Section",
        "home.body.1.value.cards.2.title": "Certification and Compliance",
        "home.body.1.value.cards.2.summary": "Follow the complete process.",
        "home.body.1.value.cards.2.link.label": "03 Certification and Compliance Follow the complete process. Visit Section",
        "home.body.1.value.cards.3.eyebrow": "Visit Section",
        "home.body.1.value.cards.3.title": "Case Studies and Ecosystem",
        "home.body.1.value.cards.3.summary": "Explore industry case studies.",
        "home.body.1.value.cards.3.link.label": "04 Case Studies and Ecosystem Explore industry case studies. Visit Section",
        # About the standard
        "pages.about.title": "About the Standard",
        "pages.about.seo_title": "About the Standard | SEMI E187",
        "pages.about.search_description": "Learn how a decade of digital transformation, legacy equipment, and the 2018 production-line cyberattack drove the need for a standardized, verifiable SEMI E187 cybersecurity language across semiconductor supply chains.",
        "pages.about.introduction": "Over the past decade, industry has accelerated digital transformation and semiconductor manufacturers have used production-line data to advance smart manufacturing. However, automated systems and equipment face end-of-support challenges, legacy software, and obsolete hardware that cannot be patched, leaving them highly vulnerable to malware and cyberattacks. A major production-line cyberattack in 2018 sounded the alarm for high-tech manufacturing. Information security has become an urgent issue for global industry and national security. Through a standardized, verifiable common language, this scheme guides industry in defining cybersecurity requirements across upstream and downstream supply chains.",
        "pages.about.section_kicker": "ABOUT SEMI E187",
        "pages.about.section_heading": "About the Standard and Its Background",
        "pages.about.body.0.value": "<p>Over the past decade, industry has accelerated digital transformation, and semiconductor manufacturers have used production-line data to advance smart manufacturing capacity. However, the semiconductor industry faces end-of-support challenges in automated systems and equipment, together with legacy software and obsolete hardware that cannot be updated or patched, leaving them highly vulnerable to malware and malicious attacks.</p><p>A major production-line cyberattack in 2018 sounded the alarm for high-tech manufacturing. Information security has become an urgent issue for global industry and national security. Through a standardized, verifiable common language, this scheme guides industry in defining cybersecurity requirements across upstream and downstream supply chains.</p>",
        "pages.about.body.1.value.heading": "The Four Key Domains of SEMI E187",
        "pages.about.body.1.value.cards.0.title": "Operating System Requirements",
        "pages.about.body.1.value.cards.0.summary": "Requires the use of long-term support releases.",
        "pages.about.body.1.value.cards.1.title": "Network Security",
        "pages.about.body.1.value.cards.1.summary": "Emphasizes secure network transmission and network configuration management.",
        "pages.about.body.1.value.cards.2.title": "Endpoint Protection",
        "pages.about.body.1.value.cards.2.summary": "Covers vulnerability scanning, malware scanning, endpoint defense mechanisms, and access control.",
        "pages.about.body.1.value.cards.3.title": "Information Security Monitoring",
        "pages.about.body.1.value.cards.3.summary": "Prioritizes the integrity and effectiveness of log records.",
        # Implementation resources
        "pages.resources.title": "Implementation Resources",
        "pages.resources.seo_title": "Implementation Resources | SEMI E187",
        "pages.resources.search_description": "Core guidance and support resources for certification-related organizations, technical laboratories, and equipment vendors.",
        "pages.resources.introduction": "Core guidance and support resources for certification-related organizations, technical laboratories, and equipment vendors.",
        "pages.resources.section_kicker": "IMPLEMENTATION RESOURCES",
        "pages.resources.section_heading": "Standard Implementation Resources",
        "pages.resources.body.0.value.heading": "Standard Implementation Resources",
        "pages.resources.body.0.value.introduction": "Core guidance and support resources for certification-related organizations, technical laboratories, and equipment vendors.",
        "pages.resources.body.0.value.cards.0.title": "Official Certification Scheme Documents",
        "pages.resources.body.0.value.cards.0.summary": "The scheme framework documents are jointly owned by the promoting organizations. This section provides a complete list of published and forthcoming official regulations.",
        "pages.resources.body.0.value.cards.0.link.label": "View Document Announcements ↓",
        "pages.resources.body.0.value.cards.1.title": "Technical Resources and Guidance",
        "pages.resources.body.0.value.cards.1.summary": "Technical guides provide in-depth explanations of the standard's framework requirements, production-network protection configurations, and best practices for host hardening.",
        "pages.resources.body.0.value.cards.1.link.label": "Browse Technical Audit Requirements →",
        "pages.resources.body.0.value.cards.2.title": "Frequently Asked Questions",
        "pages.resources.body.0.value.cards.2.summary": "Answers to common questions equipment vendors encounter during conformity testing, engineering improvements, and certificate application procedures.",
        "pages.resources.body.0.value.cards.2.link.label": "Download the FAQ Knowledge Base →",
        "pages.resources.body.1.value.heading": "Scheme Announcements and Core Regulatory Documents",
        "pages.resources.body.1.value.caption": "SEMI E187 scheme announcements and core regulatory documents list",
        "pages.resources.body.1.value.rows.0.title": "SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "pages.resources.body.1.value.rows.0.summary": "Scheme structure, roles and responsibilities, primary certification operating requirements, and post-market surveillance principles",
        "pages.resources.body.1.value.rows.0.status": "Published",
        "pages.resources.body.1.value.rows.0.link.label": "Published",
        "pages.resources.body.1.value.rows.1.title": "Semiconductor Equipment Cybersecurity Audit Requirements Based on SEMI E187",
        "pages.resources.body.1.value.rows.1.summary": "Test methods, audit items, and acceptance criteria",
        "pages.resources.body.1.value.rows.1.status": "Published",
        "pages.resources.body.1.value.rows.2.title": "Certification Operations Management Requirements for the SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "pages.resources.body.1.value.rows.2.summary": "Supporting scheme document covering certification workflows, certification-body management, and other operational details",
        "pages.resources.body.1.value.rows.2.status": "Published",
        "pages.resources.body.1.value.rows.3.title": "Certificate and Mark Management Requirements for the SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme",
        "pages.resources.body.1.value.rows.3.summary": "Requirements governing the use and restrictions of certification marks and certificates",
        "pages.resources.body.1.value.rows.3.status": "Published",
        # Certification and compliance
        "pages.certification.title": "Certification and Compliance",
        "pages.certification.seo_title": "Certification and Compliance | SEMI E187",
        "pages.certification.search_description": "Built on international conformity-assessment practices, the scheme upholds impartiality and non-discrimination so vendors receive equal treatment regardless of size. The system strictly follows ISO/IEC 17065 and ISO/IEC 17025.",
        "pages.certification.introduction": "Built on international conformity-assessment practices, the scheme upholds impartiality and non-discrimination so vendors receive equal treatment regardless of size. The system strictly follows ISO/IEC 17065 and ISO/IEC 17025.",
        "pages.certification.section_kicker": "CERTIFICATION & COMPLIANCE",
        "pages.certification.section_heading": "Certification and Compliance Center",
        "pages.certification.body.0.value": "<p>Built on international conformity-assessment practices, the scheme upholds the two principles of <strong>impartiality</strong> and <strong>non-discrimination</strong>, ensuring that vendors receive equal treatment regardless of size. The system strictly follows <strong>ISO/IEC 17065</strong> and <strong>ISO/IEC 17025</strong>.</p>",
        "pages.certification.body.1.value.heading": "Certification Bodies and Compliance Lists",
        "pages.certification.body.1.value.cards.0.eyebrow": "COMPLIANCE BODIES",
        "pages.certification.body.1.value.cards.0.title": "Approved Certification Bodies",
        "pages.certification.body.1.value.cards.0.summary": "• Taipei Computer Association (TCA) — demonstration certification body; compliant with the ISO/IEC 17065 international assessment standard",
        "pages.certification.body.1.value.cards.1.eyebrow": "AUTHORIZED LABS",
        "pages.certification.body.1.value.cards.1.title": "Approved Testing Laboratories",
        "pages.certification.body.1.value.cards.1.summary": "• Center for Measurement Standards, Industrial Technology Research Institute • Cybersecurity Technology Institute, Institute for Information Industry; compliant with ISO/IEC 17025 international testing-competence requirements",
        "pages.certification.body.1.value.cards.2.eyebrow": "COMPLIANCE LIST",
        "pages.certification.body.1.value.cards.2.title": "Certified Vendor List",
        "pages.certification.body.1.value.cards.2.summary": "A regularly announced and dynamically updated register of equipment suppliers that have passed conformity testing and expert review and successfully received SEMI E187 certificates and marks.",
        "pages.certification.body.1.value.cards.2.link.label": "Search the Online Compliance Register →",
        "pages.certification.body.2.value.heading": "Scheme Participation and Application Guide",
        "pages.certification.body.2.value.cards.0.title": "Become a Certification Body",
        "pages.certification.body.2.value.cards.0.summary": "Applicants must hold ISO/IEC 17065 accreditation and pass the management committee's rigorous assessment of semiconductor cybersecurity expertise, personnel impartiality, and audit and review capabilities.",
        "pages.certification.body.2.value.cards.0.link.label": "View Certification Body Application Requirements →",
        "pages.certification.body.2.value.cards.1.title": "Become a Testing Laboratory",
        "pages.certification.body.2.value.cards.1.summary": "Applicants must hold ISO/IEC 17025 accreditation, have equipment and dedicated testing personnel capable of assessing all four SEMI E187 domains, and complete proficiency comparison testing and competence recognition.",
        "pages.certification.body.2.value.cards.1.link.label": "View Testing Laboratory Recognition Requirements →",
        "pages.certification.body.2.value.cards.2.title": "Apply for Certification",
        "pages.certification.body.2.value.cards.2.summary": "Equipment vendors download the application package, prepare cybersecurity declaration documents (BSOM/SBOM), complete testing at an authorized laboratory, and then submit the equipment for formal review by a certification body.",
        "pages.certification.body.2.value.cards.2.link.label": "View the Vendor Certification Application Guide ↓",
        "pages.certification.body.3.value.heading": "I Am a Vendor and Want to Submit Equipment for Certification:",
        "pages.certification.body.3.value.introduction": "SEMI E187 certification process: from equipment preparation to certification",
        "pages.certification.body.3.value.steps.0.title": "Understand the Current Equipment Status",
        "pages.certification.body.3.value.steps.0.summary": "Inventory the equipment and complete necessary improvements",
        "pages.certification.body.3.value.steps.0.checklist.0": "Confirm the equipment model to be submitted",
        "pages.certification.body.3.value.steps.0.checklist.1": "Inventory the current equipment status",
        "pages.certification.body.3.value.steps.0.checklist.2": "Perform a gap analysis",
        "pages.certification.body.3.value.steps.0.checklist.3": "Complete necessary improvements",
        "pages.certification.body.3.value.steps.0.resource_links.0.label": "Cybersecurity Consulting Resources →",
        "pages.certification.body.3.value.steps.0.resource_links.1.label": "Download the SEMI E187 Compliance Checklist",
        "pages.certification.body.3.value.steps.0.resource_links.2.label": "Download Core Documents",
        "pages.certification.body.3.value.steps.1.title": "Apply for Testing",
        "pages.certification.body.3.value.steps.1.summary": "Submit a testing application to an approved laboratory",
        "pages.certification.body.3.value.steps.1.checklist.0": "Select an approved laboratory",
        "pages.certification.body.3.value.steps.1.checklist.1": "Submit the application materials",
        "pages.certification.body.3.value.steps.1.checklist.2": "Cooperate with equipment testing",
        "pages.certification.body.3.value.steps.1.checklist.3": "Obtain the test report",
        "pages.certification.body.3.value.steps.1.resource_links.0.label": "Laboratory Contact Information →",
        "pages.certification.body.3.value.steps.1.resource_links.1.label": "Application Notes →",
        "pages.certification.body.3.value.steps.1.resource_links.2.label": "Download the Testing Application Form",
        "pages.certification.body.3.value.steps.2.title": "Submit the Certification Application",
        "pages.certification.body.3.value.steps.2.summary": "Submit documents to an approved certification body for review",
        "pages.certification.body.3.value.steps.2.checklist.0": "Prepare the application documents",
        "pages.certification.body.3.value.steps.2.checklist.1": "Submit the test report",
        "pages.certification.body.3.value.steps.2.checklist.2": "Cooperate with the certification review",
        "pages.certification.body.3.value.steps.2.checklist.3": "Provide supplementary materials when necessary",
        "pages.certification.body.3.value.steps.2.resource_links.0.label": "Certification Body Contact Information →",
        "pages.certification.body.3.value.steps.2.resource_links.1.label": "Application Notes →",
        "pages.certification.body.3.value.steps.2.resource_links.2.label": "Download the Certification Application Form",
        "pages.certification.body.3.value.steps.3.title": "Obtain Certification",
        "pages.certification.body.3.value.steps.3.summary": "Receive the certificate of conformity and certification mark",
        "pages.certification.body.3.value.steps.3.checklist.0": "Cooperate with the review outcome",
        "pages.certification.body.3.value.steps.3.checklist.1": "Correct any nonconformities",
        "pages.certification.body.3.value.steps.3.checklist.2": "Receive the certificate of conformity",
        "pages.certification.body.3.value.steps.3.checklist.3": "Use the certification mark",
        "pages.certification.body.3.value.steps.4.title": "Maintain Ongoing Compliance",
        "pages.certification.body.3.value.steps.4.summary": "Cooperate with surveillance and maintain certification validity",
        "pages.certification.body.3.value.steps.4.checklist.0": "Continuously maintain equipment security",
        "pages.certification.body.3.value.steps.4.checklist.1": "Retain relevant records",
        "pages.certification.body.3.value.steps.4.checklist.2": "Cooperate with annual surveillance",
        "pages.certification.body.3.value.steps.4.checklist.3": "Maintain certification validity",
        "pages.certification.body.3.value.steps.4.resource_links.0.label": "Permitted Uses of the Certification Mark →",
        # Case studies and ecosystem
        "pages.ecosystem.title": "Case Studies and Ecosystem",
        "pages.ecosystem.seo_title": "Case Studies and Ecosystem | SEMI E187",
        "pages.ecosystem.search_description": "Building a trusted ecosystem for high-tech manufacturing supply chains, the SECPAAS platform creates a digital compliance connection platform for equipment vendors, leading wafer manufacturers, and cybersecurity service providers.",
        "pages.ecosystem.introduction": "Building a trusted ecosystem for high-tech manufacturing supply chains, the SECPAAS platform creates a digital compliance connection platform for equipment vendors, leading wafer manufacturers, and cybersecurity service providers.",
        "pages.ecosystem.section_kicker": "CASE SHARING & ECOSYSTEM",
        "pages.ecosystem.section_heading": "Case Studies and Ecosystem Development",
        "pages.ecosystem.secondary_section_kicker": "DEMONSTRATION SITES",
        "pages.ecosystem.secondary_section_heading": "Equipment Vendor Implementation Case Studies",
        "pages.ecosystem.secondary_section_introduction": "Benchmark demonstration sites showing how semiconductor equipment manufacturers implement and certify against SEMI E187.",
        "pages.ecosystem.body.0.value.heading": "Case Studies and Ecosystem Development",
        "pages.ecosystem.body.0.value.introduction": "Building a trusted ecosystem for high-tech manufacturing supply chains, the SECPAAS platform creates a digital compliance connection platform for equipment vendors, leading wafer manufacturers, and cybersecurity service providers.",
        "pages.ecosystem.body.0.value.cards.0.title": "Equipment Vendor Implementation Case Studies",
        "pages.ecosystem.body.0.value.cards.0.summary": "Selected case studies from core equipment vendors in chemical thin films, precision inspection, and smart material handling show how technical remediation was completed at the source before shipment and cybersecurity marks were obtained.",
        "pages.ecosystem.body.0.value.cards.0.link.label": "Explore Implementation Case Studies →",
        "pages.ecosystem.body.0.value.cards.1.title": "Cybersecurity Solution Provider Ecosystem Connections",
        "pages.ecosystem.body.0.value.cards.1.summary": "Connect with qualified cybersecurity technology providers offering defensive software, host-hardening modules, and secure information and event management (SIEM) solutions aligned with SEMI E187 audit criteria.",
        "pages.ecosystem.body.0.value.cards.1.link.label": "Search for Solutions →",
        "pages.ecosystem.body.1.value.case_label": "CASE STUDY 01",
        "pages.ecosystem.body.1.value.product": "AOI Automated Optical Inspection Equipment",
        "pages.ecosystem.body.1.value.certification_status": "SEMI E187 Verification of Conformity (VoC) issued by Bureau Veritas",
        "pages.ecosystem.body.1.value.summary": "By working with a cybersecurity partner to implement SEMI E187 requirements, the company strengthened equipment protection capabilities and met the supply-chain cybersecurity standards of major international semiconductor manufacturers.",
        "pages.ecosystem.body.1.value.metadata.0.label": "Industry",
        "pages.ecosystem.body.1.value.metadata.0.value": "Semiconductor equipment manufacturing",
        "pages.ecosystem.body.1.value.metadata.1.label": "Product",
        "pages.ecosystem.body.1.value.metadata.1.value": "AOI automated optical inspection equipment",
        "pages.ecosystem.body.1.value.metadata.2.label": "Project Type",
        "pages.ecosystem.body.1.value.metadata.2.value": "SEMI E187 VoC",
        "pages.ecosystem.body.1.value.metadata.3.label": "Testing Body",
        "pages.ecosystem.body.1.value.metadata.3.value": "Bureau Veritas",
        "pages.ecosystem.body.1.value.equipment_caption": "Physical view of GPM's AOI automated optical inspection equipment",
        "pages.ecosystem.body.1.value.challenge_heading": "✔ CHALLENGE",
        "pages.ecosystem.body.1.value.challenge": "<p>Customer cybersecurity requirements for supply-chain equipment are increasingly stringent. The equipment needed a security baseline based on SEMI E187 and verification that baseline protection was already in place at shipment.</p>",
        "pages.ecosystem.body.1.value.solution_heading": "✔ SOLUTION",
        "pages.ecosystem.body.1.value.solution": "<p>Working with Formosa Network Technology, the company integrated cybersecurity protection and management mechanisms aligned with SEMI E187 requirements and completed equipment conformity verification.</p>",
        "pages.ecosystem.body.1.value.security_controls_heading": "Key Cybersecurity Controls",
        "pages.ecosystem.body.1.value.security_controls.0.title": "System and Network Security",
        "pages.ecosystem.body.1.value.security_controls.0.summary": "Strengthened equipment configuration and network protection mechanisms",
        "pages.ecosystem.body.1.value.security_controls.1.title": "Endpoint Defense",
        "pages.ecosystem.body.1.value.security_controls.1.summary": "Introduced antivirus and vulnerability-scanning mechanisms",
        "pages.ecosystem.body.1.value.security_controls.2.title": "Applications and External Devices",
        "pages.ecosystem.body.1.value.security_controls.2.summary": "Controlled external interfaces and application execution",
        "pages.ecosystem.body.1.value.security_controls.3.title": "System Logging and Auditing",
        "pages.ecosystem.body.1.value.security_controls.3.summary": "Established log recording and audit-trail mechanisms",
        "pages.ecosystem.body.1.value.outcome_caption": "GPM SEMI E187 Verification of Conformity certificate (VoC)",
        "pages.ecosystem.body.2.value.case_label": "CASE STUDY 02",
        "pages.ecosystem.body.2.value.product": "OHS Automated Overhead Material Handling System",
        "pages.ecosystem.body.2.value.certification_status": "SEMI E187 Verification of Conformity (VoC) issued by Bureau Veritas",
        "pages.ecosystem.body.2.value.summary": "By implementing requirements across all four SEMI E187 domains, the company established cybersecurity protection for its automated material handling system and ensured secure, reliable operation in smart manufacturing environments.",
        "pages.ecosystem.body.2.value.metadata.0.label": "Industry",
        "pages.ecosystem.body.2.value.metadata.0.value": "Semiconductor equipment manufacturing",
        "pages.ecosystem.body.2.value.metadata.1.label": "Product",
        "pages.ecosystem.body.2.value.metadata.1.value": "OHS automated material handling system",
        "pages.ecosystem.body.2.value.metadata.2.label": "Project Type",
        "pages.ecosystem.body.2.value.metadata.2.value": "SEMI E187 VoC",
        "pages.ecosystem.body.2.value.metadata.3.label": "Testing Body",
        "pages.ecosystem.body.2.value.metadata.3.value": "Bureau Veritas",
        "pages.ecosystem.body.2.value.equipment_caption": "Physical view of Contrel Technology's OHS automated overhead material handling system",
        "pages.ecosystem.body.2.value.challenge_heading": "✔ CHALLENGE",
        "pages.ecosystem.body.2.value.challenge": "<p>Automated equipment connects to factory networks and multiple systems, requiring comprehensive cybersecurity protection and management mechanisms to meet international standards and reduce operational risk.</p>",
        "pages.ecosystem.body.2.value.solution_heading": "✔ SOLUTION",
        "pages.ecosystem.body.2.value.solution": "<p>Working with CyCraft Technology, the company introduced cybersecurity and audit management systems aligned with all four SEMI E187 domains and completed conformity verification.</p>",
        "pages.ecosystem.body.2.value.security_controls_heading": "Key Cybersecurity Controls",
        "pages.ecosystem.body.2.value.security_controls.0.title": "System and Network Security",
        "pages.ecosystem.body.2.value.security_controls.0.summary": "Strengthened network configuration and connection security management",
        "pages.ecosystem.body.2.value.security_controls.1.title": "Endpoint Defense",
        "pages.ecosystem.body.2.value.security_controls.1.summary": "Introduced vulnerability scanning and malware protection",
        "pages.ecosystem.body.2.value.security_controls.2.title": "Applications and External Devices",
        "pages.ecosystem.body.2.value.security_controls.2.summary": "Restricted external devices and application execution privileges",
        "pages.ecosystem.body.2.value.security_controls.3.title": "System Logging and Auditing",
        "pages.ecosystem.body.2.value.security_controls.3.summary": "Established log recording and audit management mechanisms",
        "pages.ecosystem.body.2.value.outcome_caption": "Contrel Technology SEMI E187 Verification of Conformity certificate (VoC)",
        "settings.title_suffix": "SEMI E187",
        "settings.brand_label": "Certification Scheme",
        "settings.site_name": "SEMI E187 Semiconductor Equipment Cybersecurity Standard",
        "settings.site_tagline": "One standard strengthens competitiveness; one mark connects the world.",
        "settings.contact_heading": "Semiconductor Smart Manufacturing Cybersecurity Compliance Consultation",
        "settings.contact_name": "Mr. Lee",
        "settings.contact_context": "Certification scheme and process",
        "settings.footer_introduction": "In support of the Ministry of Digital Affairs' cross-domain industrial cybersecurity initiative, the SECPAAS platform connects Taiwan's semiconductor equipment manufacturers with the cybersecurity supply chain. For compliance guidance or technical questions about the SEMI E187 certification process, please contact the official program office.",
        "settings.organisation_text": "© SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme. Content adapted from the official ACW guide.",
    }
)

TECHNICAL_KEYS = frozenset(
    {
        "anchor_id",
        "equipment_image",
        "layout",
        "number",
        "outcome_image",
    }
)
PRESERVED_EDITORIAL_KEYS = frozenset({"company"})
HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class TranslationCatalogError(ValueError):
    pass


def _walk_value(value, path: str, key: str = "") -> Iterator[tuple[str, str]]:
    if key in TECHNICAL_KEYS or key in PRESERVED_EDITORIAL_KEYS:
        return
    if isinstance(value, BlockImport):
        yield from _walk_value(value.value, f"{path}.value")
        return
    if isinstance(value, SourceLink):
        if value.label:
            yield f"{path}.label", value.label
        return
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            yield from _walk_value(child, f"{path}.{child_key}", child_key)
        return
    if isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            yield from _walk_value(child, f"{path}.{index}")
        return
    if isinstance(value, str) and value:
        yield path, value


def iter_editorial_strings(plan: ImportPlan) -> Iterator[tuple[str, str]]:
    for field_name in (
        "title",
        "seo_title",
        "search_description",
        "hero_badge",
        "hero_text",
        "hero_cta",
        "secondary_hero_cta",
    ):
        value = getattr(plan.home, field_name)
        if value:
            yield f"home.{field_name}", value
    yield from _walk_value(plan.home.body, "home.body")

    for page in plan.pages:
        page_path = f"pages.{page.slug}"
        for field_name in (
            "title",
            "seo_title",
            "search_description",
            "introduction",
            "section_kicker",
            "section_heading",
            "secondary_section_kicker",
            "secondary_section_heading",
            "secondary_section_introduction",
        ):
            value = getattr(page, field_name)
            if value:
                yield f"{page_path}.{field_name}", value
        yield from _walk_value(page.body, f"{page_path}.body")

    for field_name in (
        "title_suffix",
        "brand_label",
        "site_name",
        "site_tagline",
        "contact_heading",
        "contact_name",
        "contact_context",
        "footer_introduction",
        "organisation_text",
    ):
        value = getattr(plan.settings, field_name)
        if value:
            yield f"settings.{field_name}", value


def find_untranslated_paths(
    source: ImportPlan,
    catalog: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(
        path for path, _ in iter_editorial_strings(source) if path not in catalog
    )


def _translated_string(value: str, path: str, catalog: Mapping[str, str]) -> str:
    if not value:
        return value
    try:
        return catalog[path]
    except KeyError as error:
        raise TranslationCatalogError(f"Missing English translation: {path}") from error


def _translate_value(value, path: str, catalog: Mapping[str, str], key: str = ""):
    if key in TECHNICAL_KEYS or key in PRESERVED_EDITORIAL_KEYS:
        return value
    if isinstance(value, SourceLink):
        return replace(
            value,
            label=_translated_string(value.label, f"{path}.label", catalog),
        )
    if isinstance(value, Mapping):
        return {
            child_key: _translate_value(
                child,
                f"{path}.{child_key}",
                catalog,
                child_key,
            )
            for child_key, child in value.items()
        }
    if isinstance(value, (tuple, list)):
        return tuple(
            _translate_value(child, f"{path}.{index}", catalog)
            for index, child in enumerate(value)
        )
    if isinstance(value, str):
        return _translated_string(value, path, catalog)
    return value


def _translate_blocks(
    blocks: tuple[BlockImport, ...],
    path: str,
    catalog: Mapping[str, str],
) -> tuple[BlockImport, ...]:
    return tuple(
        BlockImport(
            block.type,
            _translate_value(block.value, f"{path}.{index}.value", catalog),
        )
        for index, block in enumerate(blocks)
    )


def translate_import_plan(
    source: ImportPlan,
    catalog: Mapping[str, str] = ENGLISH_CATALOG,
) -> ImportPlan:
    missing = find_untranslated_paths(source, catalog)
    if missing:
        raise TranslationCatalogError(
            "Missing English translations: " + ", ".join(missing)
        )

    home = HomeImport(
        title=catalog["home.title"],
        seo_title=catalog["home.seo_title"],
        search_description=catalog["home.search_description"],
        hero_badge=catalog["home.hero_badge"],
        hero_text=catalog["home.hero_text"],
        hero_cta=catalog["home.hero_cta"],
        hero_cta_link=source.home.hero_cta_link,
        secondary_hero_cta=catalog["home.secondary_hero_cta"],
        secondary_hero_cta_link=source.home.secondary_hero_cta_link,
        body=_translate_blocks(source.home.body, "home.body", catalog),
    )
    pages = tuple(
        PageImport(
            slug=page.slug,
            title=catalog[f"pages.{page.slug}.title"],
            seo_title=catalog[f"pages.{page.slug}.seo_title"],
            search_description=catalog[f"pages.{page.slug}.search_description"],
            introduction=catalog[f"pages.{page.slug}.introduction"],
            section_kicker=(
                catalog[f"pages.{page.slug}.section_kicker"]
                if page.section_kicker
                else ""
            ),
            section_heading=(
                catalog[f"pages.{page.slug}.section_heading"]
                if page.section_heading
                else ""
            ),
            secondary_section_kicker=(
                catalog[f"pages.{page.slug}.secondary_section_kicker"]
                if page.secondary_section_kicker
                else ""
            ),
            secondary_section_heading=(
                catalog[f"pages.{page.slug}.secondary_section_heading"]
                if page.secondary_section_heading
                else ""
            ),
            secondary_section_introduction=(
                catalog[f"pages.{page.slug}.secondary_section_introduction"]
                if page.secondary_section_introduction
                else ""
            ),
            body=_translate_blocks(
                page.body,
                f"pages.{page.slug}.body",
                catalog,
            ),
        )
        for page in source.pages
    )
    settings = SiteSettingsImport(
        title_suffix=catalog["settings.title_suffix"],
        brand_label=catalog["settings.brand_label"],
        site_name=catalog["settings.site_name"],
        site_tagline=catalog["settings.site_tagline"],
        contact_heading=catalog["settings.contact_heading"],
        contact_name=catalog["settings.contact_name"],
        contact_context=catalog["settings.contact_context"],
        contact_phone=source.settings.contact_phone,
        contact_email=source.settings.contact_email,
        footer_introduction=catalog["settings.footer_introduction"],
        organisation_text=catalog["settings.organisation_text"],
        footer_logo=source.settings.footer_logo,
        navigation_slugs=source.settings.navigation_slugs,
    )
    return replace(source, home=home, pages=pages, settings=settings)


def find_han_editorial_paths(plan: ImportPlan) -> tuple[str, ...]:
    return tuple(
        path
        for path, value in iter_editorial_strings(plan)
        if HAN_PATTERN.search(value)
    )
