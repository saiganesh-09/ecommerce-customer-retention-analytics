"""Apply the OlistDark visual theme to the generated PBIR report files.

Design-only patch: touches colors, backgrounds, borders, titles and the
page canvas. It does NOT modify queries, projections, filters, positions,
measures or any analytical content.
"""

import json
import shutil
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "powerbi" / "project" / "OlistRetention.Report"
THEME = Path(__file__).resolve().parents[1] / "powerbi" / "theme"


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def color(hex_):
    return {"solid": {"color": lit(f"'{hex_}'")}}


def main():
    # 1) register theme + background image as resource packages
    sr = P / "StaticResources" / "SharedResources" / "CustomThemes"
    sr.mkdir(parents=True, exist_ok=True)
    shutil.copy(THEME / "OlistDark.json", sr / "OlistDark.json")
    rr = P / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    shutil.copy(THEME / "bg_dark.png", rr / "bg_dark.png")

    # 2) report.json: add customTheme + resource packages
    rp = P / "definition" / "report.json"
    r = json.loads(rp.read_text())
    r["themeCollection"] = {
        "baseTheme": {
            "name": "CY20SU09",
            "reportVersionAtImport": {
                "visual": "1.8.53", "report": "2.0.53", "page": "1.3.53"},
            "type": "SharedResources"},
        "customTheme": {
            "name": "OlistDark",
            "reportVersionAtImport": {
                "visual": "1.8.53", "report": "2.0.53", "page": "1.3.53"},
            "type": "SharedResources"}}
    r["resourcePackages"] = [
        {"name": "SharedResources", "type": "SharedResources", "items": [
            {"name": "CY20SU09", "path": "BaseThemes/CY20SU09.json",
             "type": "BaseTheme"},
            {"name": "OlistDark", "path": "CustomThemes/OlistDark.json",
             "type": "CustomTheme"}]},
        {"name": "RegisteredResources", "type": "RegisteredResources",
         "items": [{"name": "bg_dark.png", "path": "bg_dark.png",
                    "type": "Image"}]}]
    rp.write_text(json.dumps(r, indent=2))

    # 3) every page: navy canvas + faint bg image
    pages = [p for p in (P / "definition" / "pages").iterdir() if p.is_dir()]
    for pd_ in pages:
        pj = json.loads((pd_ / "page.json").read_text())
        pj["objects"] = {
            "background": [{"properties": {
                "color": color("#0B1220"),
                "image": {"expr": {"ResourcePackageItem": {
                    "PackageName": "RegisteredResources",
                    "PackageType": 1, "ItemName": "bg_dark.png"}}},
                "transparency": lit("0D"),
                "imageScaling": lit("'Fit'")}}],
            "outspace": [{"properties": {"color": color("#0B1220")}}]}
        (pd_ / "page.json").write_text(json.dumps(pj, indent=2))

    # 4) visuals: dark card background + border + light title text
    n = 0
    for vj in (P / "definition" / "pages").rglob("visual.json"):
        v = json.loads(vj.read_text())
        vis = v.get("visual", {})
        # textboxes get the card treatment too - their default white
        # background is unreadable against the dark canvas
        vco = vis.setdefault("visualContainerObjects", {})
        vco["background"] = [{"properties": {
            "show": lit("true"),
            "color": color("#162338"),
            "transparency": lit("6D")}}]
        vco["border"] = [{"properties": {
            "show": lit("true"),
            "color": color("#29384D"),
            "radius": lit("8D")}}]
        if "title" in vco:
            for t in vco["title"]:
                t.setdefault("properties", {}).setdefault(
                    "fontColor", color("#F8FAFC"))
        vj.write_text(json.dumps(v, indent=2))
        n += 1

    # 5) textboxes: recolor dark text runs for the dark canvas
    #    (large bold headings -> cyan, bold labels -> white,
    #     captions -> muted, default body -> light blue-gray)
    tb = 0
    for vj in (P / "definition" / "pages").rglob("visual.json"):
        v = json.loads(vj.read_text())
        if v.get("visual", {}).get("visualType") != "textbox":
            continue
        changed = False
        for grp in v.get("visual", {}).get("objects", {}).values():
            for ps in grp:
                for p in ps.get("properties", {}).get("paragraphs", []):
                    for run in p.get("textRuns", []):
                        st = run.setdefault("textStyle", {})
                        size, weight = st.get("fontSize", ""), st.get(
                            "fontWeight", "")
                        if "16pt" in size:
                            st["color"] = "#38BDF8"      # page title
                        elif weight == "bold":
                            st["color"] = "#F8FAFC"      # section labels
                        else:
                            st["color"] = (
                                "#A8B6C8" if st.get("color") == "#666666"
                                else "#C9D6E3")
                        changed = True
        if changed:
            vj.write_text(json.dumps(v, indent=2))
            tb += 1
    print(f"patched {len(pages)} pages | styled {n} visuals | "
          f"recolored {tb} textboxes")


if __name__ == "__main__":
    main()
