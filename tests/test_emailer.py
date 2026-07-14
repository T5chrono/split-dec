"""Invitation email content: user-controlled names must be HTML-escaped."""

from _src.emailer import invitation_email_content


def test_html_escapes_user_controlled_names():
    content = invitation_email_content(
        '<script>alert(1)</script>',
        '<a href="https://evil.example">Click for a prize</a>',
    )
    assert "<script>" not in content["html"]
    assert "evil.example\">" not in content["html"]
    assert "&lt;script&gt;" in content["html"]
    assert "&lt;a href=" in content["html"]
    # The one legitimate link is ours.
    assert 'href="https://split-dec.vercel.app"' in content["html"]


def test_plain_names_render_unmangled():
    content = invitation_email_content("Tomasz & Ania", "Wyjazd — Zakopane")
    assert "Tomasz &amp; Ania" in content["html"]  # escaped entity in HTML is fine
    assert content["subject"] == "Tomasz & Ania invited you to split expenses on SplitDec"
