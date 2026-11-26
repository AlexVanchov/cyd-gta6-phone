import fonts
import inventory


def test_research_apps_parsed():
    apps = inventory.research_apps()
    assert "Contacts" in apps and "Snapmatic" in apps
    assert all("On Demand" != a for a in apps)  # unverified, not accepted


def test_font_command():
    cmd = fonts.command("x.ttf", 14, "out.bin")
    assert "--format" in cmd and "bin" in cmd and "14" in cmd and fonts.LV_FONT_CONV in cmd
