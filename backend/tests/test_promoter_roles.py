from dataclasses import replace

from app.promoter_roles import (
    EventRoleInput,
    PromoterProfile,
    classify_explicit_presenter,
    independent_profile_count,
    normalize_name,
    role_input_hash,
)


def test_venue_can_be_explicit_co_presenter():
    signal = classify_explicit_presenter("8MM", "8MM", "Romantic Fiction & 8MM present Lila Ehjä Live")
    assert signal.role == "both"
    assert signal.evidence == "8MM present"


def test_venue_match_alone_is_not_proof_of_organizer():
    signal = classify_explicit_presenter("Crack Bellmer", "Crack Bellmer", "saHHara x Tag der Clubkultur")
    assert signal.role == "unknown"
    assert signal.venue_name_match


def test_presenter_must_match_whole_name():
    assert classify_explicit_presenter("ART", "Club", "PART presents tonight").role == "unknown"
    assert classify_explicit_presenter("", None, " presents tonight").role == "unknown"


def test_normalization_handles_punctuation_and_unicode():
    assert normalize_name("://about blank") == normalize_name("About Blank")
    assert normalize_name("Ä Club") != normalize_name("A Club")


def test_event_input_hash_tracks_changes_but_not_profile_order():
    first = PromoterProfile(1, "8MM", 7)
    second = PromoterProfile(2, "Romantic Fiction")
    event = EventRoleInput(1, "8MM presents", "description", 4, "8MM", (first, second))
    assert role_input_hash(event) == role_input_hash(replace(event, promoters=(second, first)))
    assert role_input_hash(event) != role_input_hash(replace(event, title="Another title"))
    assert role_input_hash(event) != role_input_hash(replace(event, promoters=(replace(first, identity_id=None), second)))
    assert role_input_hash(event) != role_input_hash(event, version="next")


def test_only_confirmed_aliases_count_as_one_identity():
    profiles = (PromoterProfile(1, "Crack Bellmer", 42), PromoterProfile(2, "CrackBellmer", 42))
    assert independent_profile_count(profiles) == 1
    assert independent_profile_count(tuple(replace(p, identity_id=None) for p in profiles)) == 2


def test_at_venue_is_not_evidence_of_organization():
    assert classify_explicit_presenter("8MM", "8MM", "Concert at 8MM").role == "unknown"
