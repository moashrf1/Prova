import soft_skills


def test_mentioned_soft_skills_requires_two_distinct_keyword_hits():
    # Only one "Communication" keyword phrase present -- should NOT match
    assert soft_skills.mentioned_soft_skills("communicated the plan") == set()


def test_mentioned_soft_skills_detects_communication_with_two_hits():
    text = "communicated the roadmap and presented to the wider team"
    assert "Communication" in soft_skills.mentioned_soft_skills(text)


def test_mentioned_soft_skills_detects_stakeholder_management():
    text = "worked with stakeholders to get buy-in on the new plan"
    assert "Stakeholder management" in soft_skills.mentioned_soft_skills(text)


def test_mentioned_soft_skills_detects_mentoring():
    text = "mentored a junior engineer and onboarded them onto the project"
    assert "Mentoring" in soft_skills.mentioned_soft_skills(text)


def test_mentioned_soft_skills_detects_multiple_skills_at_once():
    text = (
        "negotiated a trade-off with the vendor, then prioritized the "
        "backlog for next sprint"
    )
    found = soft_skills.mentioned_soft_skills(text)
    assert "Negotiation" in found
    assert "Prioritization" in found


def test_mentioned_soft_skills_no_match_returns_empty_set():
    assert soft_skills.mentioned_soft_skills("wrote a python script") == set()


def test_mentioned_soft_skills_is_case_insensitive():
    text = "LED THE effort and drove the migration forward"
    assert "Leadership" in soft_skills.mentioned_soft_skills(text)
