from modamayor.triage import IDENTITY, build_triage_prompt, clarify_message


def test_identity_lists_address_and_location_as_answerable():
    assert "dirección y ubicación" in IDENTITY
    assert "cómo llegar" in IDENTITY


def test_identity_sends_personal_contacts_to_handoff_scope():
    assert "teléfonos o contactos personales" in IDENTITY


def test_clarify_message_mentions_address():
    assert "dirección" in clarify_message()


def test_prompt_carries_identity():
    assert IDENTITY in build_triage_prompt("La direccion", [])
